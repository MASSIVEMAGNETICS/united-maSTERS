# UnitedMasters Web UI Guide

The UnitedMasters Web UI is a Flask-based application that provides a graphical interface for the release pipeline.

## Running the Web UI Locally

To start the built-in development server:

1. Open your terminal and activate your virtual environment.
2. Run the application script:
   ```bash
   python united_masters/web/app.py
   ```
3. Open a web browser and navigate to `http://127.0.0.1:5000`.

*Note: The built-in Flask server is for development use only. For production, use a WSGI server like Gunicorn (see the public demo setup in the README).*

## Using the Dashboard

### 1. Input Configuration
- **Input Directory**: Enter the absolute path to the directory on your computer containing the audio files you want to process.
  - **Security Note**: The application restricts access to sensitive system directories (e.g., `/etc`, `/bin`, `/root`). Ensure your files are in a user-accessible location like your Documents or Music folder.

### 2. Output Settings
- **Mastering Preset**: Select the desired mastering profile from the dropdown. This dictates the target loudness and peak ceilings.
- **Export Formats**: Check the boxes for the file formats you want generated (e.g., WAV 16-bit/44.1kHz, MP3 320kbps, FLAC).

### 3. Execution
- Click **"Run Pipeline"**.
- The system will dispatch a background job to process the files. You will be redirected to a results page that auto-refreshes while the job is "running".

### 4. Viewing Results
Once complete, the UI displays a comprehensive breakdown:
- **Processed Files**: Original files and generated output paths.
- **Audio Analysis**: Detailed metrics like Duration, LUFS, True Peak, and Clipping status.
- **Quality Control (QC)**: Pass/Fail status for individual tracks and the album as a whole, listing specific warnings or errors.
- **Album Consistency**: Insights on loudness variance and sequencing suggestions across the tracks.
- **Manifest Information**: Generated release metadata including generated ISRCs.
- **Risk Score**: An overall confidence metric (0-100) indicating release readiness. Lower is better.

The physical output files, encoded deliverables, and JSON/CSV manifests will be saved in an `_output/` folder inside your specified input directory.