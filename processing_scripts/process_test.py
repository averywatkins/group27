import xml.etree.ElementTree as ET
import csv
from collections import defaultdict

# test_folder = "pan12-sexual-predator-identification-test-corpus-2012-05-21/"
test_folder = "/Users/cathuang/Desktop/pan12/pan12-test/"
truth_file = open(test_folder + "pan12-sexual-predator-identification-groundtruth-problem2.txt", "r")
conversation_id_and_line_nums = truth_file.read().splitlines()
suspicious_messages = defaultdict(list)
for conv_id_and_line_num in conversation_id_and_line_nums:
    conv_id_and_line_num_arr = conv_id_and_line_num.split()
    suspicious_messages[conv_id_and_line_num_arr[0]].append(conv_id_and_line_num_arr[1])


total_sus_words = 0;
total_words = 0
word_freq = defaultdict(lambda: [0.0, 0.0])
# print(suspicious_messages)

mytree = ET.parse(test_folder + "pan12-sexual-predator-identification-test-corpus-2012-05-17.xml")
myroot = mytree.getroot()
# print(myroot)

# idea: get words that are more prevalent in the sus msgs than in the not sus messages
# get frequency in sus message vs all messages -- those with the largest difference should be at the top

# 0.51 prob that the word is in a sus msg
# 0.49 prob that the word is in a msg
# (0.51-0.49)/0.49 more likely to be in a sus msg


# of the top x words, sort by lowest probability of being in a message and choose top 20 words
# if it's a common word, ignore it
# if it's a word that rarely appears, it's not going to be very helpful


labels = []

for conversation in myroot:
    conversationId = conversation.attrib['id']
    suspiciousConv = False
    if conversationId in suspicious_messages:
        suspiciousConv = True
    for message in conversation:
        lineNumber = message.attrib['line']
        msg = message.find('text').text
        if msg is None:
            continue
        words_in_msg = msg.split()
        total_words += len(words_in_msg)

        if (suspiciousConv and lineNumber in suspicious_messages[conversationId]):
            labels.append([msg, 1])
            for word in words_in_msg:
                word_freq[word][0] += 1.0
                word_freq[word][1] += 1.0
            total_sus_words += len(words_in_msg)
        else:
            labels.append([msg, 0])
            for word in words_in_msg:
                word_freq[word][1] += 1.0

# for word in word_freq:
#     word_freq[word][0] /= float(total_sus_words)
#     word_freq[word][1] /= float(total_words)

# sorted_word_freqs = sorted(word_freq.items(), key=lambda w:-w[1][0])[:1000]
# print(sorted_word_freqs) 
# print("!!!!!!\n\n\n!!!!!!")

# sorted_word_freqs2 = sorted(sorted_word_freqs, key=lambda w: w[1][1])
# print(sorted_word_freqs2) 


with open(test_folder + 'test_labels.csv', 'w', newline='') as f:
    writer = csv.writer(f, dialect='unix')
    writer.writerows(labels)



