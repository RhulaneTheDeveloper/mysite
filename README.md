# 🚀 Project Name (e.g., Incident Tracker or Ticket System)

A short, one-to-two sentence summary explaining what problem your application solves and who it is built for.

## 🌐 Live Demo
You can view the live application here: [https://pythonanywhere.com](https://pythonanywhere.com)

## ✨ Key Features
- **User Roles & Authentication**: Dedicated profile management with sign-in and roll assignment options.
- **Ticket Tracking**: Create, view, and track the status of submitted reports and system insights.
- **File Uploads**: Supports webp/png/jpeg images for attachments and evidence submissions.
- **Clean UI**: Uses structured HTML templates for dynamic user feedback.

## 🛠️ Tech Stack
- **Backend:** Python (Flask / Django)
- **Frontend:** HTML5, CSS3, JavaScript
- **Hosting:** PythonAnywhere
- **Version Control:** Git & GitHub

## 🚀 Local Installation & Setup

To run this project locally on your machine, follow these steps:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/RhulaneTheDeveloper/mysite.git
   cd mysite
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install the dependencies:**
   *(Note: Make sure to create a requirements.txt file if you haven't yet using `pip freeze > requirements.txt`)*
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   python app.py  # Or your main starting file name
   ```

## 📂 Project Structure
- `templates/` - Contains user layout views (`profile.html`, `track_ticket.html`, etc.).
- `uploads/` - Destination directory for client-submitted image media.
- `venv.zip` - Archive of the deployment virtual environment dependencies.
