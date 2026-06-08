// React entrypoint: mount the App into #root.
import React from "react"; // React core
import ReactDOM from "react-dom/client"; // React 18 root API
import App from "./App.jsx"; // Top-level application component
import "./styles.css"; // Global styles

// Create the React root and render the application
ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
