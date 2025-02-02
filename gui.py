import sys
import subprocess
import signal
import psutil
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QLineEdit, QPushButton, QComboBox, 
                           QLabel, QSpinBox, QCheckBox, QFormLayout,
                           QGroupBox, QTabWidget, QMessageBox, QTextEdit)
from PyQt6.QtCore import Qt, QTimer
import requests
import json
import configparser
import os
import time

class OneMinRelayControlPanel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("1Min Relay Control Panel")
        self.setMinimumWidth(600)
        
        self.server_process = None
        self.server_status_timer = QTimer()
        self.server_status_timer.timeout.connect(self.update_server_status)
        self.server_status_timer.start(5000)  # Check every 5 seconds
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Status indicator
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Server Status:")
        self.status_indicator = QLabel("Stopped")
        self.status_indicator.setStyleSheet("color: red;")
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.status_indicator)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # Create tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Server Settings Tab
        server_tab = QWidget()
        server_layout = QFormLayout(server_tab)
        
        self.host_input = QLineEdit("localhost")
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(5001)
        
        # API Key configuration
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter your 1min.ai API key")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_api_key = QPushButton("Show")
        self.show_api_key.setCheckable(True)
        self.show_api_key.toggled.connect(
            lambda checked: self.api_key_input.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        api_key_layout = QHBoxLayout()
        api_key_layout.addWidget(self.api_key_input)
        api_key_layout.addWidget(self.show_api_key)
        
        self.memcached_enabled = QCheckBox("Enable Memcached")
        self.memcached_enabled.setChecked(False)  # Disabled by default
        self.memcached_url = QLineEdit("localhost:11211")
        self.memcached_url.setEnabled(False)
        
        server_layout.addRow("Host:", self.host_input)
        server_layout.addRow("Port:", self.port_input)
        server_layout.addRow("API Key:", api_key_layout)
        server_layout.addRow("", self.memcached_enabled)
        server_layout.addRow("Memcached URL:", self.memcached_url)
        
        # Rate Limiting Settings
        rate_limit_group = QGroupBox("Rate Limiting")
        rate_limit_layout = QFormLayout()
        
        self.rate_limit_enabled = QCheckBox("Enable Rate Limiting")
        self.rate_limit_value = QSpinBox()
        self.rate_limit_value.setRange(1, 1000)
        self.rate_limit_value.setValue(500)
        self.rate_limit_period = QComboBox()
        self.rate_limit_period.addItems(["per second", "per minute", "per hour"])
        self.rate_limit_period.setCurrentText("per minute")
        
        rate_limit_layout.addRow("", self.rate_limit_enabled)
        rate_limit_layout.addRow("Limit:", self.rate_limit_value)
        rate_limit_layout.addRow("Period:", self.rate_limit_period)
        rate_limit_group.setLayout(rate_limit_layout)
        server_layout.addRow(rate_limit_group)
        
        # Model Settings Tab
        model_tab = QWidget()
        model_layout = QFormLayout(model_tab)
        
        # Model filtering settings
        model_filter_group = QGroupBox("Model Filtering")
        model_filter_layout = QFormLayout()
        
        # Add help text at the top
        help_text = QLabel(
            "This section controls which AI models are available through the relay server.\n"
            "You can either allow all models from 1min.ai or restrict to specific ones."
        )
        help_text.setWordWrap(True)
        model_filter_layout.addRow(help_text)
        
        self.permit_subset_only = QCheckBox("Only Allow Subset of Models")
        self.permit_subset_only.setToolTip(
            "When checked, only the models listed below will be available.\n"
            "When unchecked, all models from 1min.ai will be accessible."
        )
        
        self.permitted_models = QTextEdit()
        self.permitted_models.setPlaceholderText(
            "Enter the models you want to allow, separated by commas.\n\n"
            "Available models include:\n"
            "- mistral-nemo: Mistral's base model\n"
            "- gpt-4o-mini: Optimized GPT-4 variant\n"
            "- deepseek-chat: DeepSeek's chat model\n\n"
            "Example: mistral-nemo,gpt-4o-mini,deepseek-chat"
        )
        self.permitted_models.setMaximumHeight(120)  # Increased height for better visibility
        self.permitted_models.setToolTip(
            "List the specific models you want to allow.\n"
            "These must match the exact model names from 1min.ai.\n"
            "Separate multiple models with commas."
        )
        
        model_filter_layout.addRow("", self.permit_subset_only)
        model_filter_layout.addRow("Permitted Models:", self.permitted_models)
        model_filter_group.setLayout(model_filter_layout)
        model_layout.addRow(model_filter_group)
        
        # Available models section
        available_models_group = QGroupBox("Available Models")
        available_models_layout = QFormLayout()
        
        available_help = QLabel(
            "This section shows the models that are currently available through the relay.\n"
            "Click 'Refresh' to update the list from 1min.ai's servers."
        )
        available_help.setWordWrap(True)
        available_models_layout.addRow(available_help)
        
        self.model_list = QTextEdit()
        self.model_list.setPlaceholderText(
            "The list of currently available models will appear here.\n"
            "Models shown here depend on:\n"
            "1. Your 1min.ai API key permissions\n"
            "2. Your model filtering settings above\n"
            "3. Currently available models from 1min.ai"
        )
        self.model_list.setReadOnly(True)
        
        self.refresh_models_btn = QPushButton("Refresh Available Models")
        self.refresh_models_btn.setToolTip(
            "Click to fetch the current list of available models from 1min.ai.\n"
            "The server must be running to refresh the list."
        )
        
        available_models_layout.addRow(self.model_list)
        available_models_layout.addRow(self.refresh_models_btn)
        available_models_group.setLayout(available_models_layout)
        model_layout.addRow(available_models_group)
        
        # Add explanation for bolt.diy usage
        bolt_info = QLabel(
            "\nFor bolt.diy integration:\n"
            "1. Start the relay server\n"
            "2. In bolt.diy, set the API endpoint to: http://localhost:5001/v1/chat/completions\n"
            "3. You can then use any of the available models listed above"
        )
        bolt_info.setWordWrap(True)
        bolt_info.setStyleSheet("QLabel { color: #666; }")
        model_layout.addRow(bolt_info)
        
        # Add tabs
        tabs.addTab(server_tab, "Server Settings")
        tabs.addTab(model_tab, "Model Settings")
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Settings")
        self.apply_btn = QPushButton("Apply Settings")
        self.start_stop_btn = QPushButton("Start Server")
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.apply_btn)
        button_layout.addWidget(self.start_stop_btn)
        layout.addLayout(button_layout)
        
        # Connect signals
        self.memcached_enabled.stateChanged.connect(
            lambda state: self.memcached_url.setEnabled(state == Qt.CheckState.Checked.value)
        )
        self.rate_limit_enabled.stateChanged.connect(
            lambda state: self.rate_limit_value.setEnabled(state == Qt.CheckState.Checked.value)
        )
        self.save_btn.clicked.connect(self.save_settings)
        self.apply_btn.clicked.connect(self.apply_settings)
        self.start_stop_btn.clicked.connect(self.toggle_server)
        self.refresh_models_btn.clicked.connect(self.refresh_models)
        
        # Load initial settings
        self.load_settings()
        self.check_server_status()
    
    def load_settings(self):
        try:
            if os.path.exists('relay_config.ini'):
                config = configparser.ConfigParser()
                config.read('relay_config.ini')
                
                if 'Server' in config:
                    self.host_input.setText(config['Server'].get('host', 'localhost'))
                    self.port_input.setValue(int(config['Server'].get('port', '5001')))
                    self.memcached_enabled.setChecked(config['Server'].getboolean('memcached_enabled', False))
                    self.memcached_url.setText(config['Server'].get('memcached_url', 'localhost:11211'))
                    self.api_key_input.setText(config['Server'].get('api_key', ''))
                
                if 'RateLimit' in config:
                    self.rate_limit_enabled.setChecked(config['RateLimit'].getboolean('enabled', True))
                    self.rate_limit_value.setValue(int(config['RateLimit'].get('value', '500')))
                    self.rate_limit_period.setCurrentText(config['RateLimit'].get('period', 'per minute'))
                    
                if 'Models' in config:
                    self.permit_subset_only.setChecked(config['Models'].getboolean('permit_subset_only', False))
                    self.permitted_models.setPlainText(config['Models'].get('permitted_models', 'mistral-nemo,gpt-4o-mini,deepseek-chat'))
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load settings: {str(e)}")
    
    def save_settings(self):
        try:
            config = configparser.ConfigParser()
            
            config['Server'] = {
                'host': self.host_input.text(),
                'port': str(self.port_input.value()),
                'memcached_enabled': str(self.memcached_enabled.isChecked()),
                'memcached_url': self.memcached_url.text(),
                'api_key': self.api_key_input.text()
            }
            
            config['RateLimit'] = {
                'enabled': str(self.rate_limit_enabled.isChecked()),
                'value': str(self.rate_limit_value.value()),
                'period': self.rate_limit_period.currentText()
            }
            
            config['Models'] = {
                'permit_subset_only': str(self.permit_subset_only.isChecked()),
                'permitted_models': self.permitted_models.toPlainText()
            }
            
            with open('relay_config.ini', 'w') as configfile:
                config.write(configfile)
                
            QMessageBox.information(self, "Success", "Settings saved successfully!")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save settings: {str(e)}")
    
    def apply_settings(self):
        if not self.is_server_running():
            QMessageBox.warning(self, "Warning", "Server is not running. Start the server first.")
            return
            
        try:
            # Send new configuration to running server
            url = f"http://{self.host_input.text()}:{self.port_input.value()}/v1/config"
            config = {
                'memcached_enabled': self.memcached_enabled.isChecked(),
                'memcached_url': self.memcached_url.text(),
                'rate_limit': {
                    'enabled': self.rate_limit_enabled.isChecked(),
                    'value': self.rate_limit_value.value(),
                    'period': self.rate_limit_period.currentText()
                }
            }
            response = requests.post(url, json=config)
            response.raise_for_status()
            QMessageBox.information(self, "Success", "Settings applied successfully!")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to apply settings: {str(e)}")
    
    def is_server_running(self):
        if self.server_process is None:
            return False
        return self.server_process.poll() is None
    
    def check_server_status(self):
        if self.is_server_running():
            self.status_indicator.setText("Running")
            self.status_indicator.setStyleSheet("color: green;")
            self.start_stop_btn.setText("Stop Server")
        else:
            self.status_indicator.setText("Stopped")
            self.status_indicator.setStyleSheet("color: red;")
            self.start_stop_btn.setText("Start Server")
    
    def update_server_status(self):
        self.check_server_status()
        if self.is_server_running():
            try:
                url = f"http://{self.host_input.text()}:{self.port_input.value()}/v1/health"
                response = requests.get(url, timeout=1)
                if response.status_code != 200:
                    self.status_indicator.setText("Error")
                    self.status_indicator.setStyleSheet("color: orange;")
            except:
                self.status_indicator.setText("Not Responding")
                self.status_indicator.setStyleSheet("color: orange;")
    
    def toggle_server(self):
        if self.is_server_running():
            self.stop_server()
        else:
            self.start_server()
    
    def start_server(self):
        try:
            # Save current settings before starting server
            self.save_settings()
            
            # Start the server process with configuration
            server_script = os.path.join(os.path.dirname(__file__), 'main.py')
            env = os.environ.copy()
            
            # Pass configuration as environment variables
            env['RELAY_HOST'] = self.host_input.text()
            env['RELAY_PORT'] = str(self.port_input.value())
            env['RELAY_MEMCACHED_ENABLED'] = str(self.memcached_enabled.isChecked()).lower()
            env['RELAY_API_KEY'] = self.api_key_input.text()
            if self.memcached_enabled.isChecked():
                env['RELAY_MEMCACHED_URL'] = self.memcached_url.text()
            
            # Rate limiting configuration
            env['RELAY_RATE_LIMIT_ENABLED'] = str(self.rate_limit_enabled.isChecked()).lower()
            env['RELAY_RATE_LIMIT_VALUE'] = str(self.rate_limit_value.value())
            env['RELAY_RATE_LIMIT_PERIOD'] = self.rate_limit_period.currentText()
            
            # Model filtering configuration
            env['SUBSET_OF_ONE_MIN_PERMITTED_MODELS'] = self.permitted_models.toPlainText()
            env['PERMIT_MODELS_FROM_SUBSET_ONLY'] = str(self.permit_subset_only.isChecked()).lower()
            
            # Start server with the environment configuration
            self.server_process = subprocess.Popen(
                [sys.executable, server_script],
                env=env,
                # Redirect output to avoid blocking
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Wait a bit to check if server starts successfully
            time.sleep(2)
            if self.server_process.poll() is not None:
                # Server failed to start, get error message
                _, stderr = self.server_process.communicate()
                raise Exception(f"Server failed to start: {stderr}")
            
            QMessageBox.information(self, "Success", "Server started successfully!")
            self.check_server_status()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to start server: {str(e)}")
    
    def stop_server(self):
        if self.server_process:
            try:
                # Try graceful shutdown first
                self.server_process.terminate()
                try:
                    self.server_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if graceful shutdown fails
                    self.server_process.kill()
                    self.server_process.wait()
                
                self.server_process = None
                QMessageBox.information(self, "Success", "Server stopped successfully!")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to stop server: {str(e)}")
            
            self.check_server_status()
    
    def refresh_models(self):
        if not self.is_server_running():
            QMessageBox.warning(self, "Warning", "Server is not running. Start the server first.")
            return
            
        try:
            url = f"http://{self.host_input.text()}:{self.port_input.value()}/v1/models"
            response = requests.get(url)
            models = response.json()
            self.model_list.clear()
            self.model_list.setPlainText("\n".join([model['id'] for model in models['data']]))
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to refresh models: {str(e)}")
    
    def closeEvent(self, event):
        if self.server_process:
            reply = QMessageBox.question(self, 'Window Close', 'Are you sure you want to close the window? This will stop the server.',
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                self.stop_server()
                event.accept()
            else:
                event.ignore()

def main():
    app = QApplication(sys.argv)
    window = OneMinRelayControlPanel()
    window.show()
    sys.exit(app.exec()) 

if __name__ == "__main__":
    main() 