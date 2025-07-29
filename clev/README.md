# Clev Project

## Overview
Clev is a Flask web application designed to manage student information, including profiles, results, and gallery uploads. It provides functionalities for searching students, viewing their profiles, uploading results, and sending contact messages.

## Project Structure
```
clev
├── app.py                     # Main application file
├── edited_students.csv        # Contains student data
├── results.csv                # Stores student results
├── static
│   └── images
│       ├── gallery_uploads    # Directory for uploaded gallery images
│       └── results_uploads    # Directory for uploaded result PDF files
├── templates
│   ├── contact.html           # Template for the contact page
│   ├── department
│   │   ├── department.html    # Template for department information
│   │   └── department_search.html # Template for searching students by department
│   ├── gallery.html           # Template for displaying uploaded gallery images
│   ├── index.html             # Template for the homepage
│   └── profile.html           # Template for displaying student profiles and results
└── README.md                  # Documentation for the project
```

## Setup Instructions
1. **Clone the repository:**
   ```
   git clone <repository-url>
   cd clev
   ```

2. **Install dependencies:**
   Ensure you have Python installed, then install Flask and other required packages:
   ```
   pip install Flask
   ```

3. **Run the application:**
   Execute the following command to start the Flask application:
   ```
   python app.py
   ```

4. **Access the application:**
   Open your web browser and go to `http://127.0.0.1:5000` to access the application.

## Usage
- **Search for Students:** Use the search functionality on the homepage to find student profiles by admission number.
- **View Profiles:** Click on a student's profile to view their results and additional information.
- **Upload Results:** Faculty can upload student results in PDF format.
- **Contact Us:** Use the contact page to send messages or inquiries.

## Notes
- Ensure that the `edited_students.csv` and `results.csv` files are properly formatted and located in the project directory for the application to function correctly.
- The application uses SMTP for sending emails; make sure to configure the email settings in `app.py` before using the contact form.