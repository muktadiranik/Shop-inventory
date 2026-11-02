import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router';
import 'bootstrap/dist/css/bootstrap.min.css';
import './styles/app.css';
import App from './App.jsx';

ReactDOM.createRoot(document.getElementById('root')).render(
  // URL-backed filter controls must update synchronously, not in a transition.
  <React.StrictMode><BrowserRouter useTransitions={false}><App /></BrowserRouter></React.StrictMode>,
);
