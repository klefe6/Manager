# Service Manager - Trading Applications Orchestrator

A comprehensive service management and monitoring system for Hughes & Company LLC's trading applications ecosystem. This sophisticated platform provides centralized control, health monitoring, and automated service management for all trading and analysis tools, ensuring optimal performance and reliability across the entire trading infrastructure.

## Overview

The Service Manager is a professional-grade orchestration platform that manages the complete lifecycle of Hughes & Company's trading applications. It provides centralized launch capabilities, real-time health monitoring, automatic service recovery, and scheduled maintenance operations. The system is designed to maintain high availability and performance across all trading tools while providing comprehensive monitoring and alerting capabilities.

## Features

### 🚀 **Centralized Service Management**
- **Unified Launch System**: Single command to start all trading services
- **Service Orchestration**: Coordinated startup with proper sequencing
- **Cross-Platform Support**: Windows batch file integration
- **Automated Deployment**: Streamlined service deployment process

### 📊 **Advanced Health Monitoring**
- **TCP Health Checks**: Real-time service availability monitoring
- **Port Monitoring**: Comprehensive port status tracking across all services
- **Failure Detection**: Automatic identification of unhealthy services
- **Performance Metrics**: Service response time and availability tracking

### 🎯 **Intelligent Service Recovery**
- **Auto-Restart Capability**: Automatic service recovery on failures
- **Configurable Thresholds**: Customizable failure thresholds and restart policies
- **Smart Recovery Logic**: Intelligent restart sequencing and timing
- **Failure Prevention**: Proactive service health management

### 📈 **Scheduled Maintenance**
- **Daily Restart Management**: Automated daily service refresh
- **Configurable Intervals**: Flexible scheduling and timing options
- **Service-Specific Policies**: Individual service maintenance schedules
- **Maintenance Logging**: Comprehensive maintenance activity tracking

## Installation

### Prerequisites
- Python 3.8+
- Windows operating system
- Access to all trading service directories
- Network access for health monitoring

### Setup Instructions

1. **Clone the repository:**
```bash
git clone https://github.com/klefebvre6/manager.git
cd manager
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure service paths:**
Update the `SERVICES` dictionary in `launch_all_services.py` to match your local directory structure.

4. **Configure monitoring settings:**
Adjust the configuration variables at the top of `launch_all_services.py` as needed.

5. **Run the service manager:**
```bash
python launch_all_services.py
```

6. **Or use the batch file:**
```bash
reboot_all.bat
```

## Project Structure

```
Manager/
├── launch_all_services.py           # Main service management application (6.8KB)
├── reboot_all.bat                   # Windows batch launcher script (394B)
├── requirements.txt                  # Python dependencies
├── README.md                         # This documentation
└── .gitignore                        # Git ignore rules
```

## Key Components

### **launch_all_services.py** - Core Service Manager
- **Service Orchestration**: Centralized management of all trading applications
- **Health Monitoring**: Real-time TCP health checks and port monitoring
- **Auto-Recovery**: Automatic service restart on failures
- **Scheduled Maintenance**: Daily service refresh and maintenance operations

### **reboot_all.bat** - Windows Launcher
- **Batch Integration**: Windows command prompt integration
- **Service Execution**: Python script execution wrapper
- **Error Handling**: User-friendly error display and pausing
- **Directory Management**: Proper working directory setup

## Managed Services

### **Trading Applications**
- **TWIFO Sharing**: Document management and sharing system (Port 8065)
- **Import Dropbox**: Dropbox integration service (Port 8055)
- **TS Generator**: Tearsheet generation service (Port 8077)
- **TKP Tearsheet**: Advanced tearsheet analysis (Port 8076)
- **Gold Maker**: Gold trading analysis tools (Port 8075)

### **Analysis Tools**
- **Strategy Optimizer**: Trading strategy optimization (Port 8080)
- **Home Page**: Main trading dashboard (Port 8050)
- **Debug Page**: Development and debugging interface (Port 8060)
- **Sector Ratio**: Sector ratio service for market data processing (Port 8080)
- **ES Historical**: Options data analysis (Port 8071)
- **Almanac Futures**: Futures market analysis (Port 8072)

## Configuration

### **Health Monitoring Settings**
```python
HEALTH_CHECK_ENABLED   = False      # Enable/disable health monitoring
FAIL_THRESHOLD         = 2          # Consecutive failures before restart
CHECK_INTERVAL         = 15         # Seconds between health checks
```

### **Service Management Settings**
```python
DAILY_RESTART_ENABLED  = True       # Enable daily service restart
LAUNCH_PAUSE           = 3          # Seconds between service launches
DAILY_RESTART_INTERVAL = 24 * 60 * 60  # 24 hours in seconds
```

### **Service Paths**
The `SERVICES` dictionary maps each service name to its corresponding batch file path. Update these paths to match your local directory structure.

## Usage

### **Basic Service Launch**
```bash
# Launch all services at once
python launch_all_services.py

# Or use the batch file
reboot_all.bat
```

### **Health Monitoring Mode**
1. Set `HEALTH_CHECK_ENABLED = True`
2. Run the service manager
3. Monitor service health in real-time
4. Automatic recovery on failures

### **Daily Maintenance Mode**
1. Set `DAILY_RESTART_ENABLED = True`
2. Configure the service to restart daily
3. Automatic daily service refresh
4. Maintenance logging and tracking

## Technical Specifications

### **Dependencies**
- **Python Standard Library**: subprocess, os, time, socket, sys
- **No External Dependencies**: Lightweight and self-contained
- **Cross-Platform Ready**: Designed for Windows with Python

### **Network Configuration**
- **Localhost Binding**: All services run on 127.0.0.1
- **Port Management**: Comprehensive port allocation and monitoring
- **TCP Health Checks**: Reliable service availability detection
- **Timeout Handling**: Configurable connection timeouts

### **Performance Features**
- **Efficient Monitoring**: Minimal resource usage during monitoring
- **Fast Recovery**: Quick service restart and recovery
- **Scalable Architecture**: Easy to add new services
- **Resource Optimization**: Minimal memory and CPU footprint

## Service Health Monitoring

### **Health Check Methodology**
- **TCP Connection Testing**: Attempts to establish TCP connections to service ports
- **Timeout Configuration**: 5-second timeout for health checks
- **Failure Counting**: Tracks consecutive failures for each service
- **Threshold-Based Restart**: Configurable failure threshold before restart

### **Port Monitoring**
- **Comprehensive Coverage**: Monitors all 11 trading service ports
- **Real-time Status**: Continuous port availability tracking
- **Service Mapping**: Clear mapping of services to ports
- **Status Reporting**: Detailed health status reporting

## Service Recovery

### **Automatic Recovery**
- **Failure Detection**: Automatic identification of failed services
- **Smart Restart**: Intelligent restart sequencing and timing
- **Failure Prevention**: Proactive service health management
- **Recovery Logging**: Comprehensive recovery activity tracking

### **Recovery Policies**
- **Threshold-Based**: Configurable failure thresholds
- **Service-Specific**: Individual service recovery policies
- **Timing Control**: Configurable restart intervals
- **Error Handling**: Graceful error handling and recovery

## Scheduled Maintenance

### **Daily Operations**
- **Automatic Restart**: Daily service refresh for optimal performance
- **Configurable Timing**: Flexible daily restart scheduling
- **Service Selection**: Configurable service selection for daily restart
- **Maintenance Logging**: Comprehensive maintenance activity tracking

### **Maintenance Features**
- **24-Hour Cycles**: Configurable daily restart intervals
- **Service Targeting**: Specific service selection for maintenance
- **Timing Control**: Precise timing control for maintenance operations
- **Status Tracking**: Maintenance status and timing tracking

## Development

### **Code Structure**
- **Modular Design**: Clean separation of concerns
- **Configuration-Driven**: Easy configuration and customization
- **Error Handling**: Comprehensive error handling and logging
- **Professional Standards**: Production-ready code quality

### **Extensibility**
- **Service Addition**: Easy to add new services
- **Configuration Options**: Flexible configuration and customization
- **Monitoring Extensions**: Framework for additional monitoring capabilities
- **Integration Ready**: Easy integration with external monitoring systems

## Testing

### **Quality Assurance**
- **Service Validation**: Comprehensive service launch testing
- **Health Check Testing**: Port monitoring and health check validation
- **Recovery Testing**: Service restart and recovery testing
- **Integration Testing**: End-to-end service management testing

### **Error Handling**
- **Service Failures**: Graceful handling of service failures
- **Network Issues**: Robust network connectivity handling
- **Configuration Errors**: User-friendly configuration error handling
- **Recovery Mechanisms**: Reliable service recovery mechanisms

## Configuration

### **Environment Variables**
- **Service Paths**: Configurable service batch file paths
- **Port Assignments**: Flexible port allocation and configuration
- **Timing Parameters**: Configurable timing and interval settings
- **Monitoring Options**: Flexible health monitoring configuration

### **Customization Options**
- **Service Selection**: Configurable service selection and management
- **Health Check Policies**: Customizable health monitoring policies
- **Recovery Strategies**: Flexible service recovery strategies
- **Maintenance Schedules**: Configurable maintenance scheduling

## Security Features

### **Access Control**
- **Local Execution**: All services run on localhost
- **Port Isolation**: Isolated port assignments for each service
- **Service Validation**: Validation of service paths and configurations
- **Error Logging**: Secure error logging and reporting

### **Network Security**
- **Localhost Binding**: Restricted to local network access
- **Port Management**: Controlled port allocation and monitoring
- **Connection Validation**: Secure connection validation and testing
- **Service Isolation**: Isolated service execution and monitoring

## License

This project is proprietary to Hughes & Company LLC. All rights reserved.

## Contact

For questions, support, or collaboration opportunities:
- **Company**: Hughes & Company LLC
- **Email**: dhughes@hughesandco.ltd
- **Website**: www.hughesandco.ltd

## Disclaimer

This software is for educational and informational purposes only. It does not constitute investment advice. The service manager should be used as part of a comprehensive trading infrastructure management strategy. Proper testing and validation should be performed before deploying in production environments.
