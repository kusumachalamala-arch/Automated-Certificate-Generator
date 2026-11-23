from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_file,
    send_from_directory
)
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import os
import zipfile
import pandas as pd

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

from datetime import datetime

# ============================================
# Flask App Configuration
# ============================================

app = Flask(__name__)
app.secret_key = "certificate_generator_secret"

# Create required folders
os.makedirs("data", exist_ok=True)
os.makedirs("output", exist_ok=True)
os.makedirs("static/qr", exist_ok=True)


# ============================================
# Login Page
# ============================================

@app.route("/", methods=["GET", "POST"])
def login():

    if "user" in session:
        return redirect(url_for("dashboard"))

    error = None

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == "admin123":

            session["user"] = username

            return redirect(url_for("dashboard"))

        else:

            error = "Invalid Username or Password"

    return render_template(
        "login.html",
        error=error
    )

# ============================================
# Logout
# ============================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))

# ============================================
# Dashboard
# ============================================

@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect(url_for("login"))

    total_students = 0

    if os.path.exists("data/students.xlsx"):

        df = pd.read_excel("data/students.xlsx")

        total_students = len(df)

    total_certificates = 0

    if os.path.exists("output"):

        total_certificates = len(
            [
                file
                for file in os.listdir("output")
                if file.endswith(".png")
            ]
        )

    generated_today = total_certificates

    return render_template(

        "dashboard.html",

        total_students=total_students,

        total_certificates=total_certificates,

        generated_today=generated_today

    )


# ============================================
# Generate Single Certificate
# ============================================

@app.route("/single", methods=["GET", "POST"])
def single():

    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        # Get details from website form
        name = request.form.get("name", "").strip()
        course = request.form.get("course", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip()

        # Validation
        if not name or not course or not start_date or not end_date:
            flash("Please fill all fields.", "danger")
            return redirect(url_for("single"))

        # Generate certificate
        filename = generate_certificate(
            name=name,
            course=course,
            start_date=start_date,
            end_date=end_date
        )

        flash("Certificate Generated Successfully!", "success")

        return render_template(
            "single.html",
            filename=filename
        )

    return render_template("single.html")



# ============================================
# Upload Excel
# ============================================

@app.route("/upload", methods=["GET", "POST"])
def upload():

    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        file = request.files.get("excel_file")

        if not file or file.filename == "":
            return "Please select an Excel file."

        filepath = os.path.join("data", "students.xlsx")

        file.save(filepath)

        return redirect(url_for("read_excel"))

    return render_template("upload.html")


# ============================================
# View Uploaded Students
# ============================================

@app.route("/read_excel")
def read_excel():

    if "user" not in session:
        return redirect(url_for("login"))

    filepath = os.path.join("data", "students.xlsx")

    if not os.path.exists(filepath):
        return "Please upload an Excel file first."

    # Read Excel
    df = pd.read_excel(filepath)

    # Remove spaces from column names
    df.columns = df.columns.astype(str).str.strip()

    # Print column names in terminal for debugging
    print("Columns:", df.columns.tolist())

    # Convert dates only if columns exist
    if "Start Date" in df.columns:
        df["Start Date"] = pd.to_datetime(
            df["Start Date"], errors="coerce"
        ).dt.strftime("%d-%m-%Y")

    if "End Date" in df.columns:
        df["End Date"] = pd.to_datetime(
            df["End Date"], errors="coerce"
        ).dt.strftime("%d-%m-%Y")

    students = df.fillna("").to_dict(orient="records")

    return render_template(
        "students.html",
        students=students
    )

# ============================================
# Generate All Certificates
# ============================================

@app.route("/generate_all")
def generate_all():

    if "user" not in session:
        return redirect(url_for("login"))

    filepath = os.path.join("data", "students.xlsx")

    if not os.path.exists(filepath):
        return "Please upload an Excel file first."

    # Read Excel
    df = pd.read_excel(filepath)

    # Remove extra spaces from column names
    df.columns = df.columns.astype(str).str.strip()

    print("Columns:", df.columns.tolist())

    # Check required columns
    required_columns = ["Name", "Course", "Start Date", "End Date"]

    for column in required_columns:
        if column not in df.columns:
            return f"Error: Column '{column}' not found in Excel."

    # Generate certificates
    for _, row in df.iterrows():

        name = str(row["Name"]).strip()
        course = str(row["Course"]).strip()

        start_date = pd.to_datetime(
            row["Start Date"], errors="coerce"
        ).strftime("%d-%m-%Y")

        end_date = pd.to_datetime(
            row["End Date"], errors="coerce"
        ).strftime("%d-%m-%Y")

        generate_certificate(
            name=name,
            course=course,
            start_date=start_date,
            end_date=end_date
        )

    flash("All certificates generated successfully!", "success")

    return redirect(url_for("history"))

@app.route('/preview/<filename>')
def preview(filename):
    return send_from_directory("output", filename)




# ============================================
# Search Certificate
# ============================================

@app.route("/search", methods=["GET", "POST"])
def search():

    if "user" not in session:
        return redirect(url_for("login"))

    filename = None
    message = None

    if request.method == "POST":

        student_name = request.form["student_name"].strip()

        file = student_name + ".png"

        filepath = os.path.join("output", file)

        if os.path.exists(filepath):

            filename = file

        else:

            message = "Certificate Not Found"

    return render_template(

        "search.html",

        filename=filename,

        message=message

    )
# ============================================
# Generate Certificate
# ============================================

def generate_certificate(
    name,
    course,
    start_date,
    end_date
):

    template_path = os.path.join(
        "static",
        "certificate_generator.png"
    )

    certificate = Image.open(template_path)

    draw = ImageDraw.Draw(certificate)

    try:

        name_font = ImageFont.truetype(
            "arial.ttf",
            45
        )

        course_font = ImageFont.truetype(
            "arial.ttf",
            32
        )

        date_font = ImageFont.truetype(
            "arial.ttf",
            22
        )

        sign_font = ImageFont.truetype(
            "arial.ttf",
            24
        )

    except:

        name_font = ImageFont.load_default()

        course_font = ImageFont.load_default()

        date_font = ImageFont.load_default()

        sign_font = ImageFont.load_default()

    # ============================================
    # Student Name
    # ============================================

    draw.text(

        (600, 390),

        name,

        fill="black",

        font=name_font,

        anchor="mm"

    )

    # ============================================
    # Course
    # ============================================

    draw.text(

        (600, 510),

        course,

        fill="black",

        font=course_font,

        anchor="mm"

    )

    # ============================================
    # Start Date
    # ============================================

    draw.text(

        (320, 620),

        start_date,

        fill="black",

        font=date_font,

        anchor="lm"

    )

    # ============================================
    # End Date
    # ============================================

    draw.text(

        (790, 620),

        end_date,

        fill="black",

        font=date_font,

        anchor="lm"

    )

    
    # ============================================
    # Generate QR Code
    # ============================================

    

    # ============================================
    # Save Certificate
    # ============================================

    output_file = os.path.join(

        "output",

        f"{name}.png"

    )

    certificate.save(output_file)

    return output_file




# ============================================
# Download Certificate
# ============================================
@app.route("/certificate/<filename>")
def certificate(filename):
    if "user" not in session:
        return redirect(url_for("login"))

    # Extract name from the PNG filename (e.g. "KUSUMA.png" -> "KUSUMA")
    student_name = filename.replace(".png", "").strip()

    
    

    excel_path = os.path.join("data", "students.xlsx")

    if os.path.exists(excel_path):
        df = pd.read_excel(excel_path)
        
        # Clean column headers
        df.columns = df.columns.astype(str).str.strip()

        # Clean student names in Excel for exact matching
        if "Name" in df.columns:
            df["Name"] = df["Name"].astype(str).str.strip()

            # Match student name (case-insensitive)
            student = df[df["Name"].str.lower() == student_name.lower()]

            if not student.empty:
                row = student.iloc[0]

                # Get exact values using your Excel column names
                course = str(row["Course"]) if pd.notna(row.get("Course")) else ""

                if pd.notna(row.get("Start Date")):
                    start_date = pd.to_datetime(row["Start Date"]).strftime("%d-%m-%Y")

                if pd.notna(row.get("End Date")):
                    end_date = pd.to_datetime(row["End Date"]).strftime("%d-%m-%Y")

    return render_template(
        "certificate.html",
        filename=filename,
    )
@app.route("/download_certificate/<filename>")
def download_certificate(filename):

    if "user" not in session:
        return redirect(url_for("login"))

    filepath = os.path.join(
        "output",
        filename
    )

    if not os.path.exists(filepath):
        return "Certificate not found."

    return send_file(
        filepath,
        as_attachment=True
    )


# ============================================
# Download All Certificates (ZIP)
# ============================================

@app.route("/download_zip")
def download_zip():

    if "user" not in session:
        return redirect(url_for("login"))

    import tempfile

    zip_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")

    with zipfile.ZipFile(zip_file.name, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in os.listdir("output"):
            if file.endswith(".png"):
                zipf.write(os.path.join("output", file), arcname=file)

    return send_file(
        zip_file.name,
        as_attachment=True,
        download_name="certificates.zip",
        mimetype="application/zip"
    )
# ============================================
# Certificate History
# ============================================

@app.route("/history")
def history():

    if "user" not in session:
        return redirect(url_for("login"))

    os.makedirs("output", exist_ok=True)

    files = sorted(

        [

            file

            for file in os.listdir("output")

            if file.endswith(".png")

        ]

    )

    return render_template(

        "history.html",

        files=files

    )


# ============================================
# Delete Certificate
# ============================================

@app.route("/delete_certificate/<filename>")
def delete_certificate(filename):

    if "user" not in session:
        return redirect(url_for("login"))

    filepath = os.path.join(
        "output",
        filename
    )

    if os.path.exists(filepath):

        os.remove(filepath)

    return redirect(

        url_for("history")

    )
# ============================================
# Export Student Excel
# ============================================

@app.route("/export_excel")
def export_excel():

    if "user" not in session:
        return redirect(url_for("login"))

    filepath = os.path.join("data", "students.xlsx")

    if not os.path.exists(filepath):

        return "Excel file not found."

    return send_file(
        filepath,
        as_attachment=True
    )


# ============================================
# About Page
# ============================================

@app.route("/about")
def about():

    if "user" not in session:
        return redirect(url_for("login"))

    return render_template("about.html")


# ============================================
# Project Summary
# ============================================

@app.route("/summary")
def summary():

    if "user" not in session:
        return redirect(url_for("login"))

    return render_template("summary.html")


# ============================================
# 404 Error Page
# ============================================

@app.errorhandler(404)
def page_not_found(error):

    return render_template("404.html"), 404


@app.route("/download_pdf/<filename>")
def download_pdf(filename):

    if "user" not in session:
        return redirect(url_for("login"))

    image_path = os.path.join("output", filename)

    if not os.path.exists(image_path):
        return "Certificate not found."

    pdf_path = os.path.join(
        "output",
        filename.replace(".png", ".pdf")
    )

    image = ImageReader(image_path)

    c = canvas.Canvas(pdf_path)

    width, height = image.getSize()

    c.setPageSize((width, height))

    c.drawImage(image, 0, 0, width=width, height=height)

    c.save()

    return send_file(
        pdf_path,
        as_attachment=True
    )

# ============================================
# Main
# ============================================

if __name__ == "__main__":

    app.run(
        debug=True
    )