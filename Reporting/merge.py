import pandas as pd
import glob
import os

def merge_csv_to_xlsx(csv_folder, output_xlsx):
    """
    Merge multiple CSV files from a folder into a single Excel file.
    All CSV files will be combined into a single sheet in the Excel file.
    
    :param csv_folder: Path to the folder containing CSV files.
    :param output_xlsx: Path to save the output Excel file.
    """
    # Get all CSV files in the folder
    csv_files = glob.glob(os.path.join(csv_folder, "*.csv"))
    
    # Read and concatenate all CSV files
    df_list = [pd.read_csv(csv_file) for csv_file in csv_files]
    merged_df = pd.concat(df_list, ignore_index=True)
    
    # Write to Excel file
    merged_df.to_excel(output_xlsx, sheet_name="MergedData", index=False)
    
    print(f"Merged {len(csv_files)} CSV files into {output_xlsx}")

# Example usage
if __name__ == "__main__":
    csv_directory = input("Directory : ")  # Replace with the actual folder path
    output_file = "merged_output.xlsx"  # Output Excel file name
    merge_csv_to_xlsx(csv_directory, output_file)
