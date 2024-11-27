from flask import Flask, request, render_template, send_file
import pandas as pd
import os
import tempfile
import firebase_admin
from firebase_admin import credentials, storage
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Initialize Firebase Admin SDK
cred = credentials.Certificate('serviceAccountKey.json')
firebase_admin.initialize_app(cred, {'storageBucket': 'face-matply.appspot.com'})

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
            file_path = os.path.join(tempfile.gettempdir(), filename)
            file.save(file_path)

            # Upload to Firebase Storage
            bucket = storage.bucket()
            blob = bucket.blob(filename)
            blob.upload_from_filename(file_path)

            # Generate public URL (optional)
            blob.make_public()
            file_url = blob.public_url

            # Read the file to get column names (support both CSV and Excel)
            try:
                if filename.lower().endswith('.xlsx'):
                    df = pd.read_excel(file_path)
                elif filename.lower().endswith('.csv'):
                    df = pd.read_csv(file_path)
                else:
                    raise ValueError("Unsupported file format. Please upload an Excel or CSV file.")

                columns = df.columns.tolist()
                return render_template('filter.html', columns=columns, file=filename, file_url=file_url)
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

        # Download file from Firebase Storage
        bucket = storage.bucket()
        blob = bucket.blob(filename)
        file_path = os.path.join(tempfile.gettempdir(), filename)
        blob.download_to_filename(file_path)

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
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{output_format}', dir=tempfile.gettempdir())

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

        # Upload the result to Firebase Storage
        result_blob = bucket.blob(f'filtered_{filename}')
        result_blob.upload_from_filename(output_file.name)

        # Provide the file for direct download
        response = send_file(output_file.name, as_attachment=True, download_name=f'filtered_{filename}')
        return response

    except Exception as e:
        return f"Error during processing: {e}", 500


if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True)
