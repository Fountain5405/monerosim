#!/bin/bash

# This script processes log files in a specified base directory and its subdirectories.
# It reads log files, applies a sampling strategy based on file size,
# and saves the processed content to new files with a unique extension,
# leaving the original files untouched.

# Define the base directory where log files are located.
# This variable should be set to the root of your log hierarchy.
BASE_LOG_DIR="/home/lever65/monerosim_dev/monerosim/shadow.data/hosts"

# Define the unique extension for processed files
PROCESSED_EXTENSION=".processed_log"

# Function to process a single log file
# It outputs the processed content to standard output.
process_log_file() {
    local file_path="$1"
    local output_content=""

    # Check if file exists and is readable. -s checks if file exists and has size > 0.
    if [ ! -s "$file_path" ]; then
        # File is empty or does not exist, return nothing
        return
    fi

    # Get the total number of lines in the file
    local total_lines=$(wc -l < "$file_path")

    # If the file is truly empty after line counting (e.g., only newlines), return
    if (( total_lines == 0 )); then
        return
    fi

    # Logic for processing based on file size
    if (( total_lines < 1000 )); then
        # If less than 1000 lines, read the whole file
        cat "$file_path"
    else
        # Calculate chunk size (5% of total lines, max 500 lines)
        local chunk_size=$(( total_lines * 5 / 100 ))
        if (( chunk_size > 500 )); then
            chunk_size=500
        fi

        # Read the first chunk of lines
        head -n "$chunk_size" "$file_path"

        # Read the last chunk of lines
        # Ensure we don't start before the first chunk ends if the file is very compact.
        # The 'max' logic from Python is implicitly handled by tail if the file is short.
        tail -n "$chunk_size" "$file_path"

        # Generate 3 random chunks from the middle of the file
        # Define the range for random line numbers (1-indexed)
        # min_random_start: Start after the first chunk (chunk_size + 1)
        # max_random_start: End before the last chunk (total_lines - chunk_size)
        local potential_random_start_min=$(( chunk_size + 1 ))
        local potential_random_start_max=$(( total_lines - chunk_size ))

        # Ensure there's a valid range for shuf to pick from.
        # If the max is less than or equal to the min, there's no space for random chunks.
        if (( potential_random_start_max > potential_random_start_min )); then
            local num_chunks_to_sample=3
            local available_range_size=$(( potential_random_start_max - potential_random_start_min + 1 ))

            # Adjust the number of samples if the available range is too small
            if (( available_range_size < num_chunks_to_sample )); then
                num_chunks_to_sample=$available_range_size
            fi

            # Get unique random starting line numbers using shuf
            # mapfile reads lines from stdin into an array
            if (( num_chunks_to_sample > 0 )); then
                mapfile -t random_starts < <(shuf -i "$potential_random_start_min"-"$potential_random_start_max" -n "$num_chunks_to_sample")

                # For each random start, extract the chunk using sed
                for start_line in "${random_starts[@]}"; do
                    local end_line=$(( start_line + chunk_size - 1 ))
                    # sed -n 'START,ENDp' prints lines from START to END
                    sed -n "${start_line},${end_line}p" "$file_path"
                done
            fi
        fi
    fi | awk '!seen[$0]++' # Pipe all collected lines through awk for deduplication while preserving order
}

# Main script execution logic
main() {
    echo "Scanning for log files in: $BASE_LOG_DIR and its subdirectories..."

    # Use find to locate all regular files within BASE_LOG_DIR and its subdirectories
    # -type f: only regular files
    # -print0: prints file names separated by a null character, handles spaces/special chars in filenames
    # xargs -0: reads null-separated arguments
    # -I {}: placeholder for each file path
    # bash -c ...: executes a bash command for each file
    find "$BASE_LOG_DIR" -type f -print0 | while IFS= read -r -d $'\0' file_path; do
        local filename=$(basename "$file_path")
        local directory=$(dirname "$file_path")

        # Check if the file is not already a processed file
        if [[ ! "$filename" =~ \.processed_log$ ]]; then
            echo "Attempting to process: $file_path"

            # Call the processing function and capture its standard output
            local processed_content=$(process_log_file "$file_path")

            # Check if processed_content is not empty
            if [ -n "$processed_content" ]; then
                local new_filename="${filename}${PROCESSED_EXTENSION}"
                local new_file_path="${directory}/${new_filename}" # Save in the same directory as original
                # Write the processed content to the new file
                echo "$processed_content" > "$new_file_path"
                echo "Processed '$file_path' and saved to '$new_file_path'"
            elif [ -s "$file_path" ]; then # If original file had content but processed_content is empty
                echo "'$file_path' was processed but resulted in no relevant content (e.g., all lines were duplicates or stripped)."
            else # Original file was empty
                echo "Skipping empty file: '$file_path'"
            fi
        else
            echo "Skipping already processed file: $file_path"
        fi
    done

    echo "Log file processing complete."
}

# Execute the main function when the script is run
main
