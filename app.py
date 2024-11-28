from flask import Flask, request, render_template, send_file
import pandas as pd
import os
import tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Local storage directory for uploaded files
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Ensure the folder exists
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files['file']
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Debugging log
            print(f"File saved successfully at {file_path}")

            try:
                if filename.lower().endswith('.xlsx'):
                    df = pd.read_excel(file_path)
                elif filename.lower().endswith('.csv'):
                    df = pd.read_csv(file_path)
                else:
                    raise ValueError("Unsupported file format. Please upload an Excel or CSV file.")

                columns = df.columns.tolist()
                return render_template('filter.html', columns=columns, file=filename)
            except Exception as e:
                print(f"Error during file processing: {e}")
                return f"Error processing file: {e}", 400
    return render_template('index.html')


@app.route('/filter', methods=['POST'])
def filter_file():
    """
    Route to filter data by a selected column and generate a filtered file in the desired format
    (Excel or CSV), regardless of the input file type.
    """
    try:
        # Get the form data
        filter_column = request.form['filter_column']
        selected_columns = request.form.getlist('columns')
        filename = request.form['file']
        output_format = request.form['output_format']

        # Load the uploaded file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Read the file based on its extension
        if filename.lower().endswith('.xlsx'):
            df = pd.read_excel(file_path)
        elif filename.lower().endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            raise ValueError("Unsupported file format. Please upload an Excel or CSV file.")

        # Normalize column names for case-insensitive processing
        df.columns = [col.lower() for col in df.columns]

        # Map the required columns
        mapped_columns = {col.lower(): col for col in df.columns}
        missing_columns = [col for col in selected_columns if col.lower() not in mapped_columns]

        # Check for missing columns
        if missing_columns:
            raise ValueError(f"The following required columns are missing in the uploaded file: {missing_columns}")

        # Filter the data for only the required columns
        filtered_data = df[[mapped_columns[col.lower()] for col in selected_columns]]

        # Rename columns to match the desired output format
        filtered_data.columns = [col for col in selected_columns]

        # Create output file path
        output_filename = f"filtered_{os.path.splitext(filename)[0]}.{output_format}"
        output_file_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)

        # Save the filtered data in the desired format
        if output_format == 'xlsx':
            with pd.ExcelWriter(output_file_path, engine='openpyxl') as writer:
                # Create a unique sheet for each value in the filter column
                for value, value_data in filtered_data.groupby(filter_column):
                    sheet_name = str(value)[:31]  # Sheet names must be <= 31 characters
                    value_data.to_excel(writer, sheet_name=sheet_name, index=False)
        elif output_format == 'csv':
            filtered_data.to_csv(output_file_path, index=False)
        else:
            raise ValueError("Invalid output format. Please select either 'xlsx' or 'csv'.")

        # Provide the file for download
        return send_file(output_file_path, as_attachment=True, download_name=output_filename)

    except Exception as e:
        return f"Error during processing: {e}", 500



if __name__ == '__main__':
    app.run(debug=True)
