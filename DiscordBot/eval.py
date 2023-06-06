import pandas as pd
import openai
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix, accuracy_score
from gpt_classifier import generate_response
import time

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

model = AutoModelForSequenceClassification.from_pretrained('bert-base-uncased', num_labels=2)
checkpoint = torch.load('../best_model.pt')
model.load_state_dict(checkpoint['model'])
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model.to(device)

#optimizer = AdamW(model.parameters(), lr=1e-5)

def predict_text(text):
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


def get_stats(actual_scores, predicted_scores):
    accuracy = accuracy_score(actual_scores, predicted_scores)
    precision = precision_score(actual_scores, predicted_scores)
    recall = recall_score(actual_scores, predicted_scores)
    f1 = f1_score(actual_scores, predicted_scores)
    cm = confusion_matrix(actual_scores, predicted_scores)

    #with open('accuracies.txt', 'w') as file:
    #    file.write(str(accuracy) + '\n')
    print(f"Accuracy: {accuracy:.2f}%, Recall: {recall:.2f}%, Precision: {precision:.2f}%, F1 score: {f1:.2f}%")
    print(f"Confusion matrix: {cm}")
    #return accuracy
 

def evaluate_predictions(csv_file):
    actual_scores = []
    predicted_scores = []
    predicted_scores_gpt = []
    predicted_scores_bert = []

    with open(csv_file, 'r') as csvfile:
        df = pd.read_csv(csvfile, header=None)

        for index, row in df.iterrows():
            #if (index > 10):
            #    break  
            message = row.iloc[0]
            print(f"evaluating message {index}: {message}\n")
            actual_score = int(row.iloc[1])
            try:
                prediction = generate_response(message)
                print("open ai pred: ", prediction)
                time.sleep(0.01)
            except openai.error.RateLimitError as e:
                print('Error occurred:', e)
                continue
            except openai.error.APIError as e:
                print('Error occurred:', e)
                continue
            except openai.error.OpenAIError as e:
                print('Error occurred:', e)
                continue
            predicted_score = 0
            if prediction.split()[0].isdigit():
                predicted_score_1 = int(prediction.split()[0])
            else:
                print(prediction, " is not digit")
                continue
            predicted_score_2 = predict_text(message)
            if predicted_score_1 == 1:
                predicted_score = 1
            else:
                predicted_score_1 = 0
            if predicted_score_2 == 1:
                predicted_score = 1
            else:
                predicted_score_2 = 0

            actual_scores.append(actual_score)
            predicted_scores.append(predicted_score)
            predicted_scores_gpt.append(predicted_score_1)
            predicted_scores_bert.append(predicted_score_2)

    get_stats(actual_scores, predicted_scores)
    get_stats(actual_scores, predicted_scores_gpt)
    get_stats(actual_scores, predicted_scores_bert)

evaluate_predictions("../test_subset_labels.csv")


