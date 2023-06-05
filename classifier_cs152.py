# -*- coding: utf-8 -*-
"""CS152.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1jylTE5pEo3L6JydIXKPRe0WnaEq-SrKL
"""

#!pip install transformers

import csv
import sys
import random
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoTokenizer, AutoModelForSequenceClassification, AdamW
from tqdm import tqdm
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.model_selection import train_test_split

# Use BERT base uncased tokenizer and model, AdamW Optimizer with lr 1e-5
# Read more: https://huggingface.co/bert-base-uncased

tokenizer = AutoTokenizer.from_pretrained('bert-base-uncased')

model = AutoModelForSequenceClassification.from_pretrained('bert-base-uncased', num_labels=2)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model.to(device)

optimizer = AdamW(model.parameters(), lr=1e-5)

# Read in CSV dataset into 2 lists "texts" and "labels"

def load_csv_dataset(csv_file):
    csv.field_size_limit(sys.maxsize) # increase field size limit

    texts, labels = [], []
    with open(csv_file, 'r') as file:
        csv_reader = csv.reader(file)
        next(csv_reader)

        for row in csv_reader:
            try: # for first row only
                text = row[0] 
                label = int(row[1])

                if sys.getsizeof(text) > csv.field_size_limit(): continue # if field size exceeds limit, skip row

                texts.append(text)
                labels.append(int(label))

            except csv.Error: continue  # if error in parsing, skip row

    # print("Csv file:", csv_file)
    # print("Texts:", texts[0:10])
    # print("Labels:", labels[0:10])

    return texts, labels

# Read in train and test datasets, split train into train and dev datasets

train_csv = '/home/shreyaravi/pan12/pan12-train/labels.csv'
test_csv = '/home/shreyaravi/pan12/pan12-test/test_labels.csv'

train_texts, train_labels = load_csv_dataset(train_csv)
test_texts, test_labels = load_csv_dataset(test_csv)

train_texts, dev_texts, train_labels, dev_labels = train_test_split(train_texts, train_labels, test_size=0.2, random_state=42)

# Example Data #
# Note: this example data is not of the domain of interest; GPT-generated data of "suspicious vs innocent" statements.
# (Data below is not suspicious in the way that our bot defines, I know)
"""
train_texts = [
    "I saw a cute puppy today!",
    "This restaurant serves delicious food.",
    "Be careful while walking alone at night.",
    "The new movie is getting great reviews.",
    "Please avoid sharing personal information online."
]

train_labels = [0, 0, 1, 0, 1]

test_texts = [
    "I received a suspicious email today.",
    "The weather is beautiful outside.",
    "Always verify the authenticity of online sellers.",
    "The concert was amazing!",
    "Don't share your passwords with anyone."
]

test_labels = [1, 0, 1, 0, 1]

dev_texts = [
    "Exercise regularly for a healthy lifestyle.",
    "Check the reviews before making an online purchase.",
    "Never disclose sensitive information over the phone.",
    "Explore new cuisines and try unique dishes.",
    "Ensure your passwords are strong and secure."
]

dev_labels = [0, 0, 1, 0, 1]
"""

# Shuffle train and test datasets randomly, create TextDataset

class TextDataset(Dataset):
    def __init__(self, texts, labels):
        self.texts = texts
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, index):
        return self.texts[index], self.labels[index]
### Train
# Shuffle train
combined_data = list(zip(train_texts, train_labels))
random.shuffle(combined_data)
train_texts, train_labels = zip(*combined_data)

# Create train_loader
train_dataset = TextDataset(train_texts, train_labels)
train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True)

### Dev
# Shuffle dev
combined_data = list(zip(dev_texts, dev_labels))
random.shuffle(combined_data)
dev_texts, dev_labels = zip(*combined_data)

# Create dev_loader
dev_dataset = TextDataset(dev_texts, dev_labels)
dev_loader = DataLoader(dev_dataset, batch_size=8, shuffle=False)

### Test
# Shuffle test
combined_data = list(zip(test_texts, test_labels))
random.shuffle(combined_data)
test_texts, test_labels = zip(*combined_data)

# Create test_loader
test_dataset = TextDataset(test_texts, test_labels)
test_loader = DataLoader(test_dataset, batch_size=8, shuffle=False)

# Function that evaluates model with data (either dev or test set)

def model_eval(testdev_loader, model, device):
    model.eval()

    val_predictions = []
    val_targets = []

    with torch.no_grad():
        pbar = tqdm(testdev_loader, desc="Validation", leave=True)
        for texts, labels in pbar:
            texts = list(texts)
            labels = list(labels)
            encoded_inputs = tokenizer(texts, padding=True, truncation=True, return_tensors='pt')
            input_ids = encoded_inputs['input_ids'].to(device)
            attention_mask = encoded_inputs['attention_mask'].to(device)
            labels = torch.tensor(labels).to(device)

            outputs = model(input_ids, attention_mask=attention_mask)
            logits = outputs.logits
            predictions = torch.argmax(logits, dim=1)

            val_predictions.extend(predictions.cpu().numpy())
            val_targets.extend(labels.cpu().numpy())

    return val_predictions, val_targets

# Function to save model to specified filepath
def save_model(model, optimizer, filepath):
    save_info = {
        'model': model.state_dict()
    }

    torch.save(save_info, filepath)
    print(f"Saved the model to {filepath}")

# Function to finetune model
def train(train_loader, dev_loader, model, device, optimizer, tokenizer, num_epochs):
    model.train()

    best_dev_acc = 0
    for epoch in range(num_epochs):
        pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{num_epochs}", leave=True) 
        for texts, labels in pbar:
            texts = list(texts)
            labels = list(labels)
            encoded_inputs = tokenizer(texts, padding=True, truncation=True, return_tensors='pt')
            input_ids = encoded_inputs['input_ids'].to(device)
            attention_mask = encoded_inputs['attention_mask'].to(device)
            labels = torch.tensor(labels).to(device)

            outputs = model(input_ids, attention_mask=attention_mask, labels=labels)
            loss = outputs.loss

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            pbar.set_postfix({'Loss': loss.item()})
        
        val_predictions, val_targets = model_eval(dev_loader, model, device)
        dev_acc = accuracy_score(val_targets, val_predictions)
        print(f"Epoch {epoch + 1}: dev acc :: {dev_acc :.3f}")

        if dev_acc > best_dev_acc: # save best model based on dev dataset
            best_dev_acc = dev_acc
            save_model(model, optimizer, 'best_model.pt')
    
    # save last model
    save_model(model, optimizer, 'last_model.pt')

# Train model, num_epochs = 5, batch_size = 32, lr = 1e-5
train(train_loader, dev_loader, model, device, optimizer, tokenizer, num_epochs=5)

# Generate preds for given data (either dev or test set), batch_size = 32
val_predictions, val_targets = model_eval(test_loader, model, device)

# Evaluate test set on accuracy, precision, recall, and F1

accuracy = accuracy_score(val_targets, val_predictions)
precision = precision_score(val_targets, val_predictions)
recall = recall_score(val_targets, val_predictions)
f1 = f1_score(val_targets, val_predictions)

print(f"Validation Accuracy: {accuracy}")
print(f"Validation Precision: {precision}")
print(f"Validation Recall: {recall}")
print(f"Validation F1 Score: {f1}")

# Inference (for integration with Bot)

def predict_text(text):
    # load saved model
    model = AutoModelForSequenceClassification.from_pretrained('bert-base-uncased', num_labels=2)
    checkpoint = torch.load('best_model.pt')
    #checkpoint = torch.load('test_model.pt')
    model.load_state_dict(checkpoint['model'])
    model.to(device)

    # do prediction steps
    encoded_inputs = tokenizer([text], padding=True, truncation=True, return_tensors='pt')
    input_ids = encoded_inputs['input_ids'].to(device)
    attention_mask = encoded_inputs['attention_mask'].to(device)

    with torch.no_grad():
        outputs = model(input_ids, attention_mask=attention_mask)
        logits = outputs.logits
        predictions = torch.argmax(logits, dim=1)

    predicted_label = predictions.item()
    return predicted_label

# Testing inference
"""
example_texts = ["The weather is so sunny today!",
                 "Make sure all your accounts are secure."]

predictions = [predict_text(text) for text in example_texts]

for text, prediction in zip(example_texts, predictions):
    print(f"Text: {text}")
    print(f"Predicted label: {prediction}")
    print()

"""
