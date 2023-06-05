import xml.etree.ElementTree as ET
import csv

# train_folder = "pan12-sexual-predator-identification-training-corpus-2012-05-01/"
train_folder = "/Users/cathuang/Desktop/pan12/pan12-train/"
pred_id_file = open(train_folder + "pan12-sexual-predator-identification-training-corpus-predators-2012-05-01.txt", "r")
predators_id = pred_id_file.read().splitlines()
# print(predators_id)

mytree = ET.parse(train_folder + "pan12-sexual-predator-identification-training-corpus-2012-05-01.xml")
myroot = mytree.getroot()
# print(myroot)

labels = []

for conversation in myroot:
    for message in conversation:
        author = message.find('author').text
        msg = message.find('text').text
        if author in predators_id:
            labels.append([msg, 1])
        else:
            labels.append([msg, 0])

with open(train_folder + 'labels.csv', 'w', newline='') as f:
    writer = csv.writer(f, dialect='unix')
    writer.writerows(labels)



