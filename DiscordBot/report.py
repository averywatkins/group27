from enum import Enum, auto
import discord
import re

class State(Enum):
    REPORT_START = auto()
    AWAITING_MESSAGE = auto()
    MESSAGE_IDENTIFIED = auto()
    REPORT_COMPLETE = auto()
    REPORT_CANCELLED = auto()
    CONFIRM_MESSAGE = auto()
    OBTAIN_REASON = auto()
    OBTAIN_VICTIM = auto()
    VICTIM_AGE = auto()
    PERPETRATOR_AGE = auto()
    HARASSMENT_TYPE = auto()
    OTHER_HARASSMENT_TYPE = auto()
    DETECT_CSAM = auto()
    MORE_EVIDENCE = auto()

class Category(Enum):
    NULL = auto()
    HARASSMENT = auto()
    CONTENT = auto()

class Victim(Enum):
    NULL = auto()
    ME = auto()
    OTHER = auto()

class PerpAge(Enum):
    UNKNOWN = auto()
    UNDER_18 = auto()
    OVER_18 = auto()

class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"
    harassment_types = ["Blackmail", "Threats of Physical Harm", "Solicitation", "Manipulation", "Other"]

    def __init__(self, client):
        self.state = State.REPORT_START
        self.client = client
        self.message = None
        self.reported_message_link = None
        self.category = Category.NULL
        self.victim = Victim.NULL
        self.reporter = None
        self.reporter_id = None
        self.victim_age = -1
        self.perp_age = PerpAge.UNKNOWN
        self.harassment_type = []
        self.more_evidence = None
    
    async def handle_message(self, message):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord. 
        '''
        print("report for message: ", message)
        reported_message = None
        if message.content == self.CANCEL_KEYWORD:
            self.state = State.REPORT_COMPLETE
            return ["Report cancelled."]
        
        if self.state == State.REPORT_START:
            reply =  "Thank you for starting the reporting process. "
            reply += "Say `help` at any time for more information.\n\n"
            reply += "Please copy paste the link to the message you want to report.\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
            self.state = State.AWAITING_MESSAGE
            return [reply]
        
        if self.state == State.AWAITING_MESSAGE:
            # Parse out the three ID strings from the message link
            m = re.search('/(\d+)/(\d+)/(\d+)', message.content)
            self.reported_message_link = message.content
            if not m:
                return ["I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."]
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return ["I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."]
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return ["It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel."]
            try:
                message = await channel.fetch_message(int(m.group(3)))
            except discord.errors.NotFound:
                return ["It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."]

            # Here we've found the message - it's up to you to decide what to do next!
            self.state = State.CONFIRM_MESSAGE
            self.message = message
            return ["I found this message:", "```" + message.author.name + ": " + message.content + "```", \
                    "Is this the message you intended to report?"]
        

        # ask user if this is the message they intended to report -- wait for YES/NO
        if self.state == State.CONFIRM_MESSAGE:
            confirm_response = message.content.strip().lower()
            if confirm_response == "yes":
                self.reporter = message.author.name
                self.reporter_id = message.author.id
                self.state = State.MESSAGE_IDENTIFIED
            elif confirm_response == "no":
                self.state = State.AWAITING_MESSAGE
                reply = "Please copy paste the link to the message you want to report.\n"
                reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
                return [reply]
            else:
                return ["Please indicate whether this is the message you intended to report with a `yes` or `no`."]
            
        # ask user for high level category 
        if self.state == State.MESSAGE_IDENTIFIED:
            self.state = State.OBTAIN_REASON
            reply = self.prompt_options("What is the reason for reporting?", 
                               ["Sexual content involving a minor",
                                "Sexual harassment of a minor",
                                "Other"])
            return [reply]
        
        # record high level category 
        if self.state == State.OBTAIN_REASON:
            response = message.content.strip()
            reply = self.prompt_options("Who is being targeted?", ["Me", "Someone else"])
            if response == "1":
                self.category = Category.CONTENT
                self.state = State.OBTAIN_VICTIM
                return [reply]
            elif response == "2":
                self.category = Category.HARASSMENT
                self.state = State.OBTAIN_VICTIM
                return [reply]
            elif response == "3":  
                self.state = State.REPORT_COMPLETE
                return ["Thank you for submitting this report. Your report will be handled by other reporting flows."]
            else:
                reply = self.reprompt_options("What is the reason for reporting?", 
                               ["Sexual content involving a minor",
                                "Sexual harassment of a minor",
                                "Other"])
                return [reply]
        
        if self.state == State.OBTAIN_VICTIM:
            response = message.content.strip()
            if response == "1": # The reporter is the victim
                self.victim = Victim.ME
                self.state = State.VICTIM_AGE
                reply = "How old are you?"
                return [reply]
            elif response == "2":  # The victim is someone else
                self.victim = Victim.OTHER
                self.state = State.VICTIM_AGE
                reply = "How old is the victim? If you don't know, type `idk`."
                return [reply]
            else:
                reply = self.prompt_options("Who is being targeted?", ["Me", "Someone else"])
                return [reply]
            
        if self.state == State.VICTIM_AGE:
            response = message.content.strip().lower()
            prompt = "How old is the person targeting " + ("you" if self.victim == Victim.ME else "the victim") + "?"
            reply = self.prompt_options(prompt, ["Under 18", "Over 18", "I don't know"])
            if response == "idk":
                self.victim_age = -1
                self.state = State.PERPETRATOR_AGE
                return [reply]
            try:
                self.victim_age = int(response)
                if self.victim_age > 18:
                    self.state = State.REPORT_COMPLETE
                    return ["This harassment does not seem to target a minor. \n"
                            "Please restart your report and select another reason for reporting. \n"
                            "You can do this by replying 'report'."]
                self.state = State.PERPETRATOR_AGE
                return [reply]
            except ValueError:
                return ["Please enter the age as a number. If you don't know, type `idk`."]
        
        if self.state == State.PERPETRATOR_AGE:
            response = message.content.strip().lower()
            if response == "1":
                self.perp_age = PerpAge.UNDER_18
            elif response == "2":
                self.perp_age = PerpAge.OVER_18
            elif response == "3":
                self.perp_age = PerpAge.UNKNOWN
            else:
                prompt = "How old is the person targeting " + ("you" if self.victim == Victim.ME else "the victim") + "?"
                reply = self.reprompt_options(prompt, ["Under 18", "Over 18", "I don't know"])
                return [reply]
            self.state = State.HARASSMENT_TYPE
            reply = self.prompt_options_choose_many("What type of harassment is this message?",
                                ["Blackmail", "Threats of Physical Harm",
                                 "Solicitation", "Manipulation", "Other"])
            return [reply]

        if self.state == State.HARASSMENT_TYPE:
            response = message.content.strip().lower()
            for i in range(1, 5):
                if str(i) in response:
                    self.harassment_type.append(self.harassment_types[i-1])
            if "5" in response:
                self.state = State.OTHER_HARASSMENT_TYPE
                return ["You indicated `Other`. Please state the category the harassment you are reporting falls into."]
            if len(self.harassment_type) == 0:
                reply = self.reprompt_options_choose_many("What type of harassment is this message?",
                                ["Blackmail", "Threats of Physical Harm",
                                 "Solicitation", "Manipulation", "Other"])
                return [reply]
            
            self.state = State.DETECT_CSAM
            prompt = "Does the message include inappropriate images or videos? "
            prompt += "Here’s some types of content that may be considered inappropriate."
            reply = self.prompt_options(prompt, ["Yes", "No"])
            return [reply]

        if self.state == State.OTHER_HARASSMENT_TYPE:
            response = message.content.strip().lower()
            self.harassment_type.append(response)
            self.state = State.DETECT_CSAM
            prompt = "Does the message include inappropriate images or videos? "
            prompt += "Here’s some types of content that may be considered inappropriate."
            reply = self.prompt_options(prompt, ["Yes", "No"])
            return [reply]
        
        if self.state == State.DETECT_CSAM:
            response = message.content.strip().lower()
            if response == "1": 
                self.state = State.REPORT_COMPLETE
                reply = "Thank you for reporting. Our content moderation team will review your report shortly. "
                reply += "Here are some mental health resources for additional support: https://www.adolescenthealth.org/Resources/Clinical-Care-Resources/Mental-Health/Mental-Health-Resources-For-Adolesc.aspx. "
                reply += "Another way to get this image taken down **anonymously** is to report it to https://takeitdown.ncmec.org/"
                return [reply]
            elif response == "2": 
                self.state = State.MORE_EVIDENCE
                reply = "Would you like to upload further evidence? If so, please include it all in your next message. "
                reply += "If not, type `no`."
                return [reply]
            else:
                prompt = "Does the message include inappropriate images or videos? "
                prompt += "Here’s some types of content that may be considered inappropriate: https://www.inhope.org/EN/articles/child-sexual-abuse-material"
                reply = self.reprompt_options(prompt, ["Yes", "No"])
                return [reply]
            
        if self.state == State.MORE_EVIDENCE:
            response = message.content.strip().lower()
            if response != "no":
                # save the evidence for the manual review
                self.more_evidence = response

            self.state = State.REPORT_COMPLETE
            reply = "Thank you for reporting. Our content moderation team will review the report shortly. Would you like to block this user?\n"
            reply += "The user will **NOT** be notified of this action and any further attempts from this user to communicate with you will be blocked.\n"
            reply += "Follow the instructions here on how to block a user: https://support.discord.com/hc/en-us/articles/217916488-Blocking-Privacy-Settings-"
            return [reply]
        
        return []
    
    def reprompt_options_choose_many(self, prompt, options):
        reply = "Please choose at least one category.\n"
        reply += prompt + "\n"
        reply += "Please choose all types that apply. Include each number in the message (e.g. `1,2`).\n"
        reply += "\n".join(["{}. {}".format(i+1, options[i]) for i in range(len(options))])
        return reply
    
    def prompt_options_choose_many(self, prompt, options):
        reply = prompt + "\n"
        reply += "Please choose all types that apply. Include each number in the message (e.g. `1,2`).\n"
        reply += "\n".join(["{}. {}".format(i+1, options[i]) for i in range(len(options))])
        return reply
    
    def prompt_options(self, prompt, options):
        reply = prompt + "\n"
        reply += "Please reply with the corresponding number.\n"
        reply += "\n".join( ["{}. {}".format(i+1, options[i]) for i in range(len(options))] )
        return reply
    
    def reprompt_options(self, prompt, options):
        reply = "Please choose a valid number from the given options.\n"
        reply += prompt + "\n"
        reply += "Please reply with the corresponding number.\n"
        reply += "\n".join(["{}. {}".format(i+1, options[i]) for i in range(len(options))])
        return reply

    def report_complete(self):
        return self.state == State.REPORT_COMPLETE or self.state == State.REPORT_CANCELLED
    
    def report_cancelled(self):
        return self.state == State.REPORT_CANCELLED
    


    

