# 🏥 SmartCare X — Intelligent Hospital Management System

SmartCare X is a full-featured hospital management system built using **Python and Flask**.

It provides a centralized platform for managing patients, doctors, receptionists, appointments, prescriptions, medicines, billing, medical reports, and hospital administration.

The system supports both **online and offline hospital workflows** through role-based dashboards.

---

## 🚀 Key Features

### 👤 Patient

- Patient registration and login
- Email verification
- Online appointment booking
- In-person and video consultation options
- Doctor and department selection
- Appointment rescheduling and cancellation
- Digital prescriptions
- Medical reports
- Medicine bill tracking
- Online consultation and medicine payments
- Health timeline
- Patient reviews

### 🩺 Doctor

- Doctor dashboard
- Appointment management
- Appointment approval, rejection, and completion
- Doctor availability management
- Patient record management
- Digital prescription creation
- Medicine selection
- Dosage and frequency management
- Automatic medicine stock deduction
- Patient medical history
- Video consultation access

### 🧑‍💼 Receptionist

- Walk-in patient registration
- Patient lookup
- Appointment management
- Automatic token assignment
- Consultation billing
- Counter billing
- Cash, card, and UPI payment handling
- Live token board

### 🛡️ Admin

- Admin dashboard
- User management
- Doctor management
- Department management
- Medicine inventory management
- Appointment management
- Refund management
- Revenue reports
- Appointment reports
- CSV/PDF report exports
- Contact message management
- Audit logs
- Financial record management

---

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| **Python** | Backend development and business logic |
| **Flask** | Web application framework |
| **SQL / SQLAlchemy** | Database management and relationships |
| **HTML** | Web page structure |
| **CSS** | Custom styling and responsive UI |
| **Bootstrap** | Responsive layouts and UI components |
| **Flask-Login** | User authentication |
| **Flask-Mail** | Email notifications |
| **Flask-Migrate** | Database migrations |
| **ReportLab** | PDF report generation |
| **Razorpay** | Online payment processing |
| **Jitsi Meet** | Video consultation |
| **APScheduler** | Automated background tasks |

---

## 🗄️ Database

SmartCare X uses a relational database for managing structured hospital data.

The database manages:

- Patients
- Doctors
- Users and roles
- Departments
- Appointments
- Prescriptions
- Medicines
- Inventory
- Bills
- Payments
- Medical reports
- Reviews
- Notifications
- Audit records

Database relationships keep appointments, patients, doctors, prescriptions, billing, and medical records connected.

---

## 🏗️ Application Architecture

SmartCare X follows a modular Flask application structure.

```text
app.py
   │
   ▼
Application Factory
   │
   ▼
Configuration
   │
   ▼
Flask Extensions
   │
   ▼
Blueprints
   ├── Main
   ├── Authentication
   ├── Patient
   ├── Doctor
   ├── Reception
   └── Admin
   │
   ▼
Business Logic / Services
   │
   ▼
Database Models
   │
   ▼
SQL Database