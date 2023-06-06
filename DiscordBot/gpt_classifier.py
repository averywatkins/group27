import openai
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score

#openai.organization = "org-YVZe9QFuR0Ke0J0rqr7l2R2L"
#openai.api_key = open("openai-key.txt", "r").readline()
open("openai-key.txt", "r").close()


def remove_dups():
    df = pd.read_csv('../test_subset_labels.csv')
    df = df.drop_duplicates()
    df.to_csv('output_labels.csv', index=False)


def generate_response(conversation):

    preamble = "We are building a direct messaging platform and would like to ensure that it is safe for minors. " \
               "We are specifically hoping to combat child sexual abuse and grooming. " \
               "Please review this message and output a score it 0 or 1 based on the likelihood " \
               "that it might contain sexual abuse of a minor. 0 is for an innocent message and 1 is for a suspicious " \
               "message. For example: \n" \
               "A phrase with a score of 1 would be: `Just send me the photos. " \
               "I promise I won’t save them. Trust me`\n" \
               "A phrase with a score of 0 would be: `Happy birthday!`\n Evaluate the following message." \
               "Only output number 0 or 1: \n"
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": f"{preamble}{conversation}"}]
    )
    
    '''
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=f"{preamble}{conversation}"
    )
    '''

    return response["choices"][0]['message']['content']


def evaluate_predictions():
    actual_scores = []
    predicted_scores = []

    with open("../test_subset_labels.csv", 'r') as csvfile:
        reader = csv.reader(csvfile)
        sampled_df = pd.read_csv(csvfile, header=None)
        #sampled_df = df.sample(n=100000)

        i = 1
        for index, row in sampled_df.iterrows():
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
                predicted_score = int(prediction)
            print(f"GPT response: {predicted_score}")

            actual_scores.append(actual_score)
            predicted_scores.append(predicted_score)

            i += 1

    accuracy = (sum(1 for i in range(len(actual_scores)) if actual_scores[i] == predicted_scores[i]) / len(actual_scores)) * 100
    precision = precision_score(actual_scores, predicted_scores)
    recall = recall_score(actual_scores, predicted_scores)
    f1 = f1_score(actual_scores, predicted_scores)

    with open('accuracies.txt', 'w') as file:
        file.write(str(accuracy) + '\n')
    print(f"Accuracy: {accuracy:.2f}%, Recall: {recall:.2f}%, Precision: {precision:.2f}%, F1 score: {f1:.2f}%")
    return accuracy
