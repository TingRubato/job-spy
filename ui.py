from flask import Flask, render_template, request
import subprocess
import shlex

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/runscript', methods=['POST'])
def run_script():
    job_keywords = request.form['job_keywords']
    location_keywords = request.form['location_keywords']

    # Convert the comma-separated strings to lists
    job_keywords_list = job_keywords.split(';')
    location_keywords_list = location_keywords.split(';')

    # Construct the command to run your script with arguments
    # Assuming your Python script is named 'your_script.py'
    cmd = f"python ./script/job_scrapping.py --position {' '.join(job_keywords_list)} --location {' '.join(location_keywords_list)}"

    # Execute the command and capture the output
    process = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    # Send the output back to the web page
    return render_template('output.html', output=stdout.decode(), error=stderr.decode())

if __name__ == '__main__':
    app.run(debug=True)
