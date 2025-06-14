import os
import sys
import re

# Add project root to the Python path to allow running this script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.flexr.utils.milvus_util import MilvusUtil, SearchResults, SearchResult

common_questions = [
    "Can I change my bank account details?",
    "Can I change my payment date?",
    "Can I change my payment period?",
    "Can I add a new authority to the account?",
    "What information do you hold about me?",
    "Is my account active?",
    "Can I get my bond refunded?",
    "Do you mind us asking why you are thinking of closing your account?",
    "How do I order a new card?",
    "Can I order another card?",
    "Can I cancel a card?",
    "Can I suspend my card?",
    "Can the courier leave my card without a signature?",
    "How long will my card take to arrive?",
    "Why has my card not arrived?",
    "Can I use my card straight away?",
    "What is the limit on my card?",
    "Can I change the card limit?",
    "Can we preload the card?",
    "Why is my card not working?",
    "Why did my card decline?",
    "Can you replace my card?",
    "What is my pin?",
    "I've forgotten my pin.",
    "Why does my invoice say that I am getting no discount?",
    "Is this a promo discount? Will my discount decrease after 6 months?",
    "Why is my discount different from what I expected?",
    "Why don't I get the same discount at all the fuel companies?",
    "Can I get a better discount?",
    "What discount do I get?",
    "How does National Pricing work?",
    "How can I make a payment on my account?",
    "Can I pay by credit card? How much will it cost to use it?",
    "When is my payment due?",
    "When is the payment coming out of my account?",
    "How much do I owe?",
    "Can you take my payment out?",
    "Can we pay our invoice in advance?",
    "When will I receive my invoice?",
    "I've paid my bill, why is it saying I'm over the monthly limit of the card?",
    "Can I apply as an individual?",
    "I don't have a business - can I still apply?",
    "Why did you refuse my application?",
    "Do I need to provide my DL (Driver's License)?",
    "What if I don't have a driver's license?",
    "Where can I use my fuel cards?",
    "Can I use my card at… (specific fuel supplier)?",
    "Where can I use the card?",
    "Are truckstops cheaper? Am I allowed to use them?",
    "Can I buy cigarettes with my card?",
    "What card will give me the cheapest fuel?",
    "What is the best card for me?",
    "Which card is best for me to use?",
    "What are the limits on my card?",
    "How do daily limits work?",
    "Can I change my restrictions?",
    "When can my restrictions change?",
    "Do you have an app?",
    "Can we see our information online?",
    "I'm not receiving my emails.",
    "Does my rewards card work with this discount?",
    "How much money on average could I save a year?",
    "What are my transactions from… (period of time)?",
    "Can I load my Smiles card against my account?",
    "Can we specify a vehicle for the card?",
    "Will you remove the finance statement?",
    "Can I have my FS (Financial Statement) released?",
    "Do you accept payments over the phone?"
]
test_questions = [
    "How do i refund?",
]

def write_to_file(results: list[tuple[float, str, str]], question: str, file_name: str):
    # Append the results for each question to the file
    with open(file_name, "a") as f:
        if not results:
            f.write(f"\n{'*'*20} {question} {'*'*20}\n")
            f.write("No results found.\n")
        
        f.write(f"\n{'-'*20} {question} {'-'*20}\n")
        for result in results:
            # Access attributes of the SearchResult object
            threshold = 0.5
            highlight_score = f"{result[0]:.3f}"
            if result[0] < threshold:
                highlight_score = f"**{result[0]:.3f}**"
           
            f.write(f"Score: {highlight_score}\tPage: {result[1]}\nContent: {re.sub(r'\s+',' ',result[2])}\n")
            f.write("\n")
            # print(f"Score: {highlight_score}\tPage: {result[1]}\nContent: {re.sub(r'\s+',' ',result[2])}\n")
            # print("\n")


def benchmark_questions():
    milvus_util = MilvusUtil()
    # Overwrite the file at the start of the benchmark
    with open("benchmark_questions.txt", "w") as f:
        f.write("--- Benchmark Results By Milvus ---\n")
    with open("benchmark_questions_reranked.txt", "w") as f:
        f.write("--- Benchmark Results Reranked By Cohere ---\n")

    no_result_count = 0
    low_result_count = 0
    low_rerank_count = 0

    questions = common_questions

    for question in questions:
        # The 'search' method returns a SearchResults object
        results = milvus_util._test_search(question)
        if len(results) == 0:
            no_result_count += 1
        elif results[0][0] < 0.5:
            low_result_count += 1
        # Pass the list of results to the writing function
        write_to_file(results[:2], question, "benchmark_questions.txt")
        reranked_results = milvus_util._test_rerank(question, results)
        if len(reranked_results) > 0:
            if reranked_results[0][0] < 0.5:
                low_rerank_count+=1
        write_to_file(reranked_results, question, "benchmark_questions_reranked.txt")
    
    with open("benchmark_questions.txt", "a") as f:
        f.write(f"No result percentage: {no_result_count/len(questions)}\n")
        f.write(f"Low similarity result percentage: {low_result_count/len(questions)}\n")
    with open("benchmark_questions_reranked.txt", "a") as f:
        f.write(f"Low similarity rerank result percentage: {low_rerank_count/len(questions)}\n")
    

    print("Benchmark finished. Results are in benchmark_questions.txt")

if __name__ == "__main__":
    benchmark_questions()

