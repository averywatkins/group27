import csv
import sys
import random
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoTokenizer, AutoModelForSequenceClassification, AdamW
from tqdm import tqdm
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.model_selection import train_test_split

tokenizer = AutoTokenizer.from_pretrained('bert-base-uncased')

#model = AutoModelForSequenceClassification.from_pretrained('bert-base-uncased', num_labels=2)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
#model.to(device)

#optimizer = AdamW(model.parameters(), lr=1e-5)

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

while(True):
    print(predict_text(input()))
