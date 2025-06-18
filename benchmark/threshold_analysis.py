import pandas as pd
import numpy as np
from sklearn.metrics import precision_recall_curve, f1_score, precision_score, recall_score

def get_manual_relevance_assessment(df):
    """
    Interactively prompts the user to provide a relevance assessment for each row in the dataset.
    'hr' (Highly Relevant) is treated as the positive class (1), while all others are negative (0).
    """
    ground_truth = []
    print("--- Starting Manual Relevance Assessment ---")
    print("Please assess the relevance based on the query and content summary:")
    print("Enter 'hr' for Highly Relevant")
    print("Enter 'pr' for Partially Relevant")
    print("Enter 'ir' for Irrelevant")
    print("-" * 40)

    for index, row in df.iterrows():
        query = row['query']
        # Display only the first 200 characters of the content as a summary
        content_summary = row['content'][:200] + '...' if len(row['content']) > 200 else row['content']
        
        print(f"\nAssessing entry {index + 1}/{len(df)}:")
        print(f"  Query: {query}")
        print(f"  Content Summary: {content_summary}")
        
        assessment = ''
        while assessment not in ['hr', 'pr', 'ir']:
            assessment = input("Enter your assessment (hr/pr/ir): ").lower().strip()
            if assessment not in ['hr', 'pr', 'ir']:
                print("Invalid input. Please enter 'hr', 'pr', or 'ir'.")

        # Based on our analysis model, only "Highly Relevant" is treated as a True Positive.
        if assessment == 'hr':
            ground_truth.append(1)
        else:
            ground_truth.append(0)
            
    df['ground_truth'] = ground_truth
    print("\n--- Manual Assessment Complete ---")
    return df

def find_optimal_threshold(df):
    """
    Calculates precision, recall, and F1-score for different thresholds and finds the optimal one.
    The optimal threshold is the one that maximizes the F1-score.
    """
    print("Calculating optimal threshold...")
    
    y_true = df['ground_truth']
    y_scores = df['relevance']

    # Use precision_recall_curve to get precision and recall for all possible thresholds
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_scores)

    # Exclude cases where precision and recall are both 0 to avoid division by zero in F1 score calculation
    # The length of 'thresholds' is one less than 'precisions' and 'recalls'
    f1_scores = [2 * p * r / (p + r) if (p + r) > 0 else 0 for p, r in zip(precisions[:-1], recalls[:-1])]
    
    # Find the index of the maximum F1 score
    if not f1_scores: # Handle cases where f1_scores is empty
        return 0, 0, 0, 0

    best_f1_index = np.argmax(f1_scores)
    
    # Get the optimal values
    best_f1_score = f1_scores[best_f1_index]
    # The threshold corresponds to the F1 score at that index.
    best_threshold = thresholds[best_f1_index]
    best_precision = precisions[best_f1_index]
    best_recall = recalls[best_f1_index]
    
    return best_threshold, best_f1_score, best_precision, best_recall

def main():
    """
    Main function to execute the entire analysis workflow.
    """
    # --- Configuration ---
    # Please replace 'temp.xlsx' with the path to your Excel file.
    file_path = './temp.xlsx'
    
    try:
        # Try to read an Excel file, fall back to CSV if it fails
        try:
            df = pd.read_excel(file_path)
        except (ValueError, ImportError):
            df = pd.read_csv(file_path)
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found. Please ensure the filename is correct and the file is in the same directory as the script.")
        return

    # Step 1: Perform manual relevance assessment
    df_assessed = get_manual_relevance_assessment(df)
    
    # Check if there are any positive samples, otherwise, calculation is not possible
    if 1 not in df_assessed['ground_truth'].unique():
        print("\nError: No samples were marked as 'Highly Relevant' (hr) in your assessment.")
        print("Cannot calculate precision, recall, and F1-score to recommend a threshold.")
        print("Please mark at least one result you consider highly relevant as 'hr' and try again.")
        return

    # Step 2: Find the optimal threshold
    threshold, f1, precision, recall = find_optimal_threshold(df_assessed)

    # Step 3: Print the final report
    print("\n" + "="*45)
    print("      Optimal Threshold Analysis Report")
    print("="*45)
    print(f"\nAnalysis complete. Based on your assessments, the recommended relevance score threshold is:\n")
    print(f"  >> Recommended Threshold: {threshold:.4f}\n")
    print("At this threshold, the system's performance metrics are as follows:")
    print(f"  - F1-Score:  {f1:.4f} (Higher is better; a balance between Precision and Recall)")
    print(f"  - Precision: {precision:.4f} (Measures the accuracy of the returned results)")
    print(f"  - Recall:    {recall:.4f} (Measures the coverage of relevant results)")
    print("\n" + "="*45)
    print("\nNote: This threshold represents the best trade-off between prioritizing accuracy (high precision) and ensuring comprehensive coverage (high recall).")

if __name__ == '__main__':
    main()
