import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import Models from './pages/Models';
import ModelDetail from './pages/ModelDetail';
import Alerts from './pages/Alerts';
import Calibration from './pages/Calibration';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        
        {/* Protected Routes wrapped in Layout */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout>
                <Dashboard />
              </Layout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/models"
          element={
            <ProtectedRoute>
              <Layout>
                <Models />
              </Layout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/models/:id"
          element={
            <ProtectedRoute>
              <Layout>
                <ModelDetail />
              </Layout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/alerts"
          element={
            <ProtectedRoute>
              <Layout>
                <Alerts />
              </Layout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/calibration"
          element={
            <ProtectedRoute>
              <Layout>
                <Calibration />
              </Layout>
            </ProtectedRoute>
          }
        />
        
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}