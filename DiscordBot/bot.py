# bot.py
import discord
from discord.ext import commands
import os
import json
import logging
import re
import requests
from report import Report, PerpAge, AutomatedReport
from enum import Enum, auto
from collections import defaultdict
from classifier_cs152 import predict_text
from gpt_classifier import generate_response
import pdb

# Set up logging to the console
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# There should be a file called 'tokens.json' inside the same folder as this file
token_path = 'tokens.json'
if not os.path.isfile(token_path):
    raise Exception(f"{token_path} not found!")
with open(token_path) as f:
    # If you get an error here, it means your token is formatted incorrectly. Did you put it in quotes?
    tokens = json.load(f)
    discord_token = tokens['discord']

class ModState(Enum):
    MOD_START = auto()
    AWAITING_MESSAGE = auto()
    REVIEW_OBTAINED = auto()
    REVIEW_COMPLETE = auto()
    SPAM_UNDETECTED = auto()
    AUTO_REVIEW_OBTAINED = auto()
    VERIFY_POLICY_VIOLATION = auto()
    REVIEW_VISUAL_CONTENT = auto()
    DETECT_CSAM = auto()
    VERIFY_ABUSE_TYPE = auto()
    CHECK_PHYSICAL_THREAT = auto()

class Review:
    START_KEYWORD = "review"
    CANCEL_KEYWORD = "cancel"

class ModBot(discord.Client):
    def __init__(self): 
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='.', intents=intents)
        self.group_num = None
        self.mod_channels = {}  # Map from guild to the mod channel id for that guild
        self.reports = {}  # Map from user IDs to the state of their report
        self.automated_reports = {}
        self.curr_auto_report = None
        self.current_report = None
        self.past_reports = defaultdict(list)
        self.reported_users = defaultdict(int)
        self.spam_accounts = set()
        self.suspended_accounts = set()
        self.pending_moderation = {'level1': [], 'level2': [], 'level3': [], 'level4': [], 'level5': []}
        self.mod_state = ModState.MOD_START

    async def on_ready(self):
        print(f'{self.user.name} has connected to Discord! It is these guilds:')
        for guild in self.guilds:
            print(f' - {guild.name}')
        print('Press Ctrl-C to quit.')

        # Parse the group number out of the bot's name
        match = re.search('[gG]roup (\d+) [bB]ot', self.user.name)
        if match:
            self.group_num = match.group(1)
        else:
            raise Exception("Group number not found in bot's name. Name format should be \"Group # Bot\".")

        # Find the mod channel in each guild that this bot should report to
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == f'group-{self.group_num}-mod':
                    self.mod_channels[guild.id] = channel
        

    async def on_message(self, message):
        '''
        This function is called whenever a message is sent in a channel that the bot can see (including DMs). 
        Currently the bot is configured to only handle messages that are sent over DMs or in your group's "group-#" channel. 
        '''
        # Ignore messages from the bot 
        if message.author.id == self.user.id:
            return

        # Check if this message was sent in a server ("guild") or if it's a DM
        if message.guild:
            await self.handle_channel_message(message)
        else:
            await self.handle_dm(message)

    async def handle_dm(self, message):
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply = "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report process.\n"
            await message.channel.send(reply)
            return

        author_id = message.author.id
        responses = []

        # Only respond to messages if they're part of a reporting flow
        if author_id not in self.reports and not message.content.startswith(Report.START_KEYWORD):
            return

        # If we don't currently have an active report for this user, add one
        if author_id not in self.reports:
            self.reports[author_id] = Report(self)

        # Let the report class handle this message; forward all the messages it returns to uss
        responses = await self.reports[author_id].handle_message(message)
        for r in responses:
            await message.channel.send(r)

        # If the report is complete or cancelled, remove it from our map
        if self.reports[author_id].report_complete():
            if not self.reports[author_id].report_cancelled():
                self.past_reports[author_id].append(self.reports[author_id])
                self.reported_users[self.reports[author_id].message.author.id] += 1
                # add report to pending moderations before it is popped off the queue
                self.classify_report(self.reports[author_id])
            
            self.reports.pop(author_id)

    async def handle_channel_message(self, message):
        # Only handle messages sent in the "group-#" channel
        if message.channel.name == f'group-{self.group_num}-mod':
            responses = await self.do_moderation(message)
            for r in responses:
                await message.channel.send(r)

        if message.channel.name == f'group-{self.group_num}':
            score1 = predict_text(message)
            score2 = int(generate_response(message))
            print(score2)
            if score1 == 1 or score2 == 1:
                print("suspicious!")
                reply = "This is message is being marked as suspicious for grooming/sexual harassment of a minor!"
                author_id = message.author.id
                if author_id not in self.automated_reports:
                    self.automated_reports[author_id] = AutomatedReport(self)
                    await self.automated_reports[author_id].handle_message(message)
                    self.pending_moderation['level5'].append(self.automated_reports[author_id])
                await message.channel.send(reply)

        '''
        Not needed for now. We want to stop forwarding.
        mod_channel = self.mod_channels[message.guild.id]
        await mod_channel.send(f'Forwarded message:\n{message.author.name}: "{message.content}"')
        scores = self.eval_text(message.content)
        await mod_channel.send(self.code_format(scores))'''

    async def do_moderation(self, message):
        # Only handle messages sent in the "group-#-mod" channel
        # This is the channel for the moderator.
        if not message.channel.name == f'group-{self.group_num}-mod':
            return

        danger_level = 0

        if message.content == Review.CANCEL_KEYWORD:
            self.mod_state = ModState.REVIEW_COMPLETE
            return ["Review cancelled."]

        if self.mod_state == ModState.REVIEW_COMPLETE:
            self.mod_state = ModState.MOD_START

        if self.mod_state == ModState.MOD_START:
            if not message.content.startswith(Review.START_KEYWORD):
                reply = "Welcome moderator! Please type `review` to begin moderation or `cancel` to stop moderation"
                return [reply]
            else:
                reply = "Thank you for starting the moderation process. "
                reply += "Say `help` at any time for more information.\n\n"

            for level in range(1, 5):
                print(self.pending_moderation)
                if len(self.pending_moderation[f'level{level}']):
                    self.current_report = self.pending_moderation[f'level{level}'][0]
                    danger_level = level
                    self.pending_moderation[f'level{level}'].pop(0)
                    self.mod_state = ModState.REVIEW_OBTAINED
                    break
            if self.mod_state != ModState.REVIEW_OBTAINED:
                if len(self.pending_moderation[f'level5']):
                    self.curr_auto_report = self.pending_moderation[f'level5'][0]
                    self.pending_moderation[f'level5'].pop(0)
                    reply += "There is a message automatically detected to be reviewed at this time.\n"
                    self.mod_state = ModState.AUTO_REVIEW_OBTAINED
                else:
                    reply += "There are no reports to be moderated at this time. Thank you!"
                    self.mod_state = ModState.REVIEW_COMPLETE
                    return [reply]

        if self.mod_state == ModState.REVIEW_OBTAINED:
            # clarify this part once we know how to save multiple reports made by the same user
            if len(self.past_reports[self.current_report.reporter_id]) > 5:
                print("Spam detected - user flagged")
                reply = "This reporter has made over 5 reports and is most likely a spam reporter"
                self.spam_accounts.add(self.current_report.reporter_id)
                self.mod_state = ModState.REVIEW_COMPLETE  # for now. Definitely change later. Give next report
                return [reply]
            else:
                self.mod_state = ModState.SPAM_UNDETECTED

        if self.mod_state == ModState.AUTO_REVIEW_OBTAINED:
            harassment_types = ", ".join(self.curr_auto_report.harassment_type)
            reply = "We want to warn you that the content you are about to review might potentially contain some " \
                    "disturbing depictions of child sexual abuse/harassment. Please take care of yourself and take a " \
                    "break if you need one.\n\n"
            reply += f"This report is a report made by our automatic detector.\nUser {self.curr_auto_report.perpatrator} is " \
                     f"being flagged on the basis of {harassment_types}.\n The message in question" \
                     f" is {self.curr_auto_report.message.content}.\n Here is a link to the conversation for more context:" \
                     f" \n {self.curr_auto_report.reported_message_link}.\n Does this message violate any company security policies?"
            self.current_report = self.curr_auto_report
            self.mod_state = ModState.VERIFY_POLICY_VIOLATION
            return [reply]

        if self.mod_state == ModState.SPAM_UNDETECTED:
            harassment_types = ", ".join(self.current_report.harassment_type)
            reply = "We want to warn you that the content you are about to review might potentially contain some " \
                    "disturbing depictions of child sexual abuse/harassment. Please take care of yourself and take a " \
                    "break if you need one.\n\n"
            reply += f"This report is a Level {danger_level} report.\nUser {self.current_report.reporter} has reported user " \
                    f"{self.current_report.message.author.name} on the basis of {harassment_types}.\n The message in question" \
                    f" is: {self.current_report.message.content}.\n Here is a link to the conversation for more context:" \
                    f" \n {self.current_report.reported_message_link}.\n " \
                    f" This report is currently classified as potential child sexual abuse including {harassment_types}. \n" \
                    f" Do you think that this abuse type is correct?  \n" \
                    f" Please reply yes or no."
            self.mod_state = ModState.VERIFY_ABUSE_TYPE
            return [reply]

        if self.mod_state == ModState.VERIFY_ABUSE_TYPE:
            response = message.content.strip().lower()
            if response == "no":
                reply = f"You have noted that this report is not related to child sexual abuse. \n " \
                        f"As such, it is out of the scope of this bot and will sent to other reporting flows"
                self.mod_state = ModState.REVIEW_COMPLETE
                return [reply]
            elif response == "yes":
                reply = "Does this message violate any company child safety policies?"
                if self.current_report.more_evidence is not None:
                    reply += f"More evidence is provided by the reporter as follows: \n {self.current_report.more_evidence}"
                    return [reply]
                self.mod_state = ModState.VERIFY_POLICY_VIOLATION
                return [reply]
            else:
                reply = "Please respond with `yes` or `no`."
                return [reply]

        if self.mod_state == ModState.VERIFY_POLICY_VIOLATION:
            response = message.content.strip().lower()
            if response == "no":
                self.mod_state = ModState.REVIEW_COMPLETE
                reply = "No further action necessary. The reporter will be asked if they want to block this user."
                return [reply]
            elif response == "yes":
                reply = "Does the message contain images or videos?"
                self.mod_state = ModState.REVIEW_VISUAL_CONTENT
                return [reply]
            else:
                reply = "Please respond with `yes` or `no`."
                return [reply]

        # response to does this include photos/videos
        if self.mod_state == ModState.REVIEW_VISUAL_CONTENT:
            response = message.content.strip().lower()
            if response == "no":
                self.mod_state = ModState.CHECK_PHYSICAL_THREAT
                reply = f"Does the abuse include a legitimate threat of physical harm?\n"
                return [reply]
            elif response == "yes":
                self.mod_state = ModState.DETECT_CSAM
                reply = "Does the message contain CSAM? Saying `yes` will cause the image to be hashed against " \
                        "known CSAM and, if previously unknown, to be reported to NCMEC" \
                        "The reported account to will also be automatically banned and reported to local authorities."
                return [reply]
            else:
                reply = "Please respond with `yes` or `no`."
                return [reply]

        # response to does this include CSAM
        if self.mod_state == ModState.DETECT_CSAM:
            response = message.content.strip().lower()
            if response == "no":
                self.mod_state = ModState.CHECK_PHYSICAL_THREAT
                reply = f"Does the abuse include a legitimate threat of physical harm?\n"
                return [reply]
            elif response == "yes":
                reply = "The reported account has been automatically banned and reported to authorities. " \
                        "The image has been hashed into NCMEC."
                self.mod_state = ModState.REVIEW_COMPLETE
                return [reply]
            else:
                reply = "Please respond with `yes` or `no`."
                return [reply]

        # response to the question does this include a threat of physical harm
        if self.mod_state == ModState.CHECK_PHYSICAL_THREAT:
            response = message.content.strip().lower()
            if response == "no":
                if self.current_report.message.author.id in self.suspended_accounts:
                    reply = "The reported account has been automatically banned for being previously suspended" \
                            " in other abuse cases."
                    self.mod_state = ModState.REVIEW_COMPLETE
                    return [reply]
                else:
                    reply = "This case is under review for the appropriate suspension duration. Until a final decision " \
                            "is reached, the reported account is banned for 3 months." # for now default is 3 months
                    self.suspended_accounts.add(self.current_report.message.author.id)
                    self.mod_state = ModState.REVIEW_COMPLETE
                    return [reply]
            elif response == "yes":
                reply = "The reported account has been automatically banned and reported to authorities."
                self.mod_state = ModState.REVIEW_COMPLETE
                return [reply]
            else:
                reply = "Please respond with `yes` or `no`."
                return [reply]

    def classify_report(self, report):
        # Classifies reports made by the user to one of 4 levels
        print(self.reported_users)
        print(report.message.author.name, report.message.author.id)

        if self.reported_users[report.message.author.id] > 2:
            self.pending_moderation['level1'].append(report)
        elif report.victim_age <= 13:
            if report.perp_age == PerpAge.OVER_18:
                self.pending_moderation['level2'].append(report)
            else:
                self.pending_moderation['level3'].append(report)
        else:
            self.pending_moderation['level4'].append(report)

    def eval_text(self, message):
        ''''
        TODO: Once you know how you want to evaluate messages in your channel, 
        insert your code here! This will primarily be used in Milestone 3. 
        '''
        return message

    
    def code_format(self, text):
        ''''
        TODO: Once you know how you want to show that a message has been 
        evaluated, insert your code here for formatting the string to be 
        shown in the mod channel. 
        '''
        return "Evaluated: '" + text+ "'"


client = ModBot()
client.run(discord_token)