from flask import Flask, request, render_template, send_file
import pandas as pd
import os
import tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = 'results'


# Ensure the upload and result directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULT_FOLDER'] = RESULT_FOLDER

@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Home route to upload file and select filtering options.
    """
    if request.method == 'POST':
        # Handle file upload
        file = request.files['file']
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Read the file to get column names (support both CSV and Excel)
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
                return f"Error processing file: {e}", 400

    return render_template('index.html')
@app.route('/filter', methods=['POST'])
def filter_file():
    """
    Route to filter data by a selected column and generate a filtered file with unique sheets for each value in the filter column.
    """
    try:
        # Get the form data
        filter_column = request.form['filter_column']
        selected_columns = request.form.getlist('columns')
        filename = request.form['file']
        output_format = request.form['output_format']

        # Read the uploaded file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if filename.lower().endswith('.xlsx'):
            df = pd.read_excel(file_path)
        elif filename.lower().endswith('.csv'):
            df = pd.read_csv(file_path)

        # Normalize the column names in the input data for comparison
        df.columns = [col.lower() for col in df.columns]

        # Map the required columns
        mapped_columns = {col.lower(): col for col in df.columns}
        missing_columns = [col for col in selected_columns if col.lower() not in mapped_columns]

        # Check for missing columns
        if missing_columns:
            raise ValueError(f"The following required columns are missing in the Excel file: {missing_columns}")

        # Filter the data for only the required columns
        filtered_data = df[[mapped_columns[col.lower()] for col in selected_columns]]

        # Rename columns to match the desired output format
        filtered_data.columns = [col for col in selected_columns]

        # Create a new file for filtered data in memory
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{output_format}', dir=app.config['RESULT_FOLDER'])

        if output_format == 'xlsx':
            with pd.ExcelWriter(output_file.name, engine='openpyxl') as writer:
                # Create a unique sheet for each value in the filter column
                for value, value_data in filtered_data.groupby(filter_column):
                    sheet_name = str(value)[:31]  # Sheet names must be <= 31 characters
                    value_data.to_excel(writer, sheet_name=sheet_name, index=False)
        elif output_format == 'csv':
            with open(output_file.name, 'w', newline='', encoding='utf-8') as f:
                # Write the filtered data to a CSV
                filtered_data.to_csv(f, index=False)

        # Provide a download link for the result file
        return send_file(output_file.name, as_attachment=True, download_name=f'filtered_{filename}')

    except Exception as e:
        return f"Error during processing: {e}", 500

if __name__ == '__main__':
    app.run(debug=True)
