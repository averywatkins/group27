import pandas as pd
import openai
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix, accuracy_score
from gpt_classifier import generate_response
from classifier_cs152 import predict_text


def evaluate_predictions(csv_file):
    actual_scores = []
    predicted_scores = []

    with open(csv_file, 'r') as csvfile:
        df = pd.read_csv(csvfile, header=None, skiprows=100)

        for index, row in df.iterrows():
            message = row.iloc[0]
            print(f"evaluating message {i}: {message}\n")
            actual_score = int(row.iloc[1])
            try:
                prediction = generate_response(message)
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
            if prediction.isdigit():
                predicted_score_1 = int(prediction)
            predicted_score_2 = predict_text(message)
            if predicted_score_1 == 1 or predicted_score_2 == 1:
                predicted_score = 1

            actual_scores.append(actual_score)
            predicted_scores.append(predicted_score)

    accuracy = accuracy_score(actual_scores, predicted_scores)
    precision = precision_score(actual_scores, predicted_scores)
    recall = recall_score(actual_scores, predicted_scores)
    f1 = f1_score(actual_scores, predicted_scores)
    cm = confusion_matrix(actual_scores, predicted_scores)

    with open('accuracies.txt', 'w') as file:
        file.write(str(accuracy) + '\n')
    print(f"Accuracy: {accuracy:.2f}%, Recall: {recall:.2f}%, Precision: {precision:.2f}%, F1 score: {f1:.2f}%")
    print(f"Confusion matrix: {cm}")
    return accuracy
