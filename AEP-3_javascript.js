// AEP-3_javascript.js

// Import necessary modules
const express = require('express');
const bodyParser = require('body-parser');
const mongoose = require('mongoose');

// Connect to MongoDB database
mongoose.connect('mongodb://localhost:27017/rbac', { useNewUrlParser: true, useUnifiedTopology: true });
const db = mongoose.connection;
db.on('error', console.error.bind(console, 'connection error:'));
db.once('open', function() {
  console.log("Connected to MongoDB");
});

// Define role schema and model
const roleSchema = new mongoose.Schema({
  name: String,
  permissions: [String]
});
const Role = mongoose.model('Role', roleSchema);

// Middleware for RBAC
const checkRole = (role) => {
  return (req, res, next) => {
    if (req.user.role !== role) {
      return res.status(403).json({ message: "Unauthorized" });
    }
    next();
  };
};

// Define routes
const app = express();
app.use(bodyParser.json());

// API endpoint for employee
app.get('/employee', checkRole('employee'), (req, res) => {
  res.json({ message: "Employee route accessed" });
});

// API endpoint for manager
app.get('/manager', checkRole('manager'), (req, res) => {
  res.json({ message: "Manager route accessed" });
});

// API endpoint for admin
app.get('/admin', checkRole('admin'), (req, res) => {
  res.json({ message: "Admin route accessed" });
});

// Error handling middleware
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ message: "Internal Server Error" });
});

// Start server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

// AEP-3: Role-Based Access Control (RBAC) system - Javascript code for role-based permissions and access enforcement.