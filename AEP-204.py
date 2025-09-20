# Issue: AEP-204
# Generated: 2025-09-20T06:48:25.312024
# Thread: 8067122d
# Enhanced: LangChain structured generation
# AI Model: deepseek/deepseek-chat-v3.1:free
# Max Length: 25000 characters


import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Container from '@mui/material/Container';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import Snackbar from '@mui/material/Snackbar';
import Dashboard from './components/Dashboard';
import DataView from './components/DataView';
import Settings from './components/Settings';
import Navigation from './components/Navigation';
import { AppContext } from './context/AppContext';
import { logger } from './utils/logger';
import { validateInput } from './utils/validators';
import './App.css';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    background: {
      default: '#f5f5f5',
    },
  },
  typography: {
    h4: {
      fontWeight: 600,
    },
  },
});

const App = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [data, setData] = useState([]);
  const [userPreferences, setUserPreferences] = useState({});

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/aep/data', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      
      if (validateInput(result, 'aepData')) {
        setData(result);
        logger.info('Data fetched successfully');
      } else {
        throw new Error('Invalid data format received from server');
      }
    } catch (err) {
      logger.error('Failed to fetch data:', err);
      setError('Failed to load data. Please try again later.');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchUserPreferences = useCallback(async () => {
    try {
      const response = await fetch('/api/user/preferences', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const preferences = await response.json();
      setUserPreferences(preferences);
      logger.info('User preferences loaded');
    } catch (err) {
      logger.warn('Failed to load user preferences:', err);
    }
  }, []);

  useEffect(() => {
    const initializeApp = async () => {
      try {
        await Promise.all([fetchData(), fetchUserPreferences()]);
      } catch (err) {
        logger.error('App initialization failed:', err);
        setError('Application initialization failed');
      }
    };

    initializeApp();
  }, [fetchData, fetchUserPreferences]);

  const handleErrorClose = () => {
    setError(null);
  };

  const handleSuccessClose = () => {
    setSuccess(null);
  };

  const updateData = useCallback(async (newData) => {
    try {
      setLoading(true);
      const response = await fetch('/api/aep/data', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(newData),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      setData(result);
      setSuccess('Data updated successfully');
      logger.info('Data updated successfully');
    } catch (err) {
      logger.error('Failed to update data:', err);
      setError('Failed to update data. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  const updatePreferences = useCallback(async (newPreferences) => {
    try {
      const response = await fetch('/api/user/preferences', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(newPreferences),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const updatedPreferences = await response.json();
      setUserPreferences(updatedPreferences);
      setSuccess('Preferences updated successfully');
      logger.info('User preferences updated');
    } catch (err) {
      logger.error('Failed to update preferences:', err);
      setError('Failed to update preferences. Please try again.');
    }
  }, []);

  const contextValue = {
    data,
    userPreferences,
    loading,
    updateData,
    updatePreferences,
    setError,
    setSuccess,
  };

  if (loading) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
          <CircularProgress />
        </Box>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppContext.Provider value={contextValue}>
        <Router>
          <Box sx={{ display: 'flex' }}>
            <Navigation />
            <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
              <Container maxWidth="xl">
                <Routes>
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/data" element={<DataView />} />
                  <Route path="/settings" element={<Settings />} />
                  <Route path="*" element={<Navigate to="/dashboard" replace />} />
                </Routes>
              </Container>
            </Box>
          </Box>
        </Router>
      </AppContext.Provider>

      <Snackbar
        open={!!error}
        autoHideDuration={6000}
        onClose={handleErrorClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleErrorClose} severity="error" sx={{ width: '100%' }}>
          {error}
        </Alert>
      </Snackbar>

      <Snackbar
        open={!!success}
        autoHideDuration={3000}
        onClose={handleSuccessClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleSuccessClose} severity="success" sx={{ width: '100%' }}>
          {success}
        </Alert>
      </Snackbar>
    </ThemeProvider>
  );
};

export default App;