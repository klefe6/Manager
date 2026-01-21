# PM2 Monitor for Windows Batch Files

A Python-based process manager that automatically restarts your Windows batch files every hour, similar to PM2 for Node.js applications.

## Features

- **Hourly Restarts**: Automatically restarts all configured services every hour
- **Process Management**: Tracks and kills existing processes before restarting
- **Health Monitoring**: Continuously monitors service health via TCP port checks
- **Comprehensive Logging**: Detailed logs with timestamps and status information
- **Graceful Shutdown**: Properly terminates processes on shutdown
- **Configurable**: Easy-to-modify configuration for different environments

## Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Monitor**:
   ```bash
   python pm2_monitor.py
   ```
   
   Or use the batch file:
   ```bash
   start_pm2_monitor.bat
   ```

3. **Stop the Monitor**: Press `Ctrl+C` in the terminal

## Configuration

Edit `pm2_config.py` to customize the monitor behavior:

### Core Settings
- `HOURLY_RESTART_ENABLED`: Enable/disable hourly restarts (default: True)
- `HEALTH_CHECK_ENABLED`: Enable/disable health monitoring (default: True)
- `RESTART_INTERVAL`: Time between restarts in seconds (default: 3600 = 1 hour)
- `HEALTH_CHECK_INTERVAL`: Health check frequency in seconds (default: 30)

### Service Configuration
- `SERVICES`: Dictionary mapping service names to batch file paths
- `PORTS`: Dictionary mapping service names to (host, port) tuples for health checks

### Example Configuration
```python
# Change restart interval to 30 minutes
RESTART_INTERVAL = 30 * 60

# Add a new service
SERVICES["New Service"] = r"C:\Path\To\Your\service.bat"
PORTS["New Service"] = ("127.0.0.1", 8080)

# Disable health monitoring
HEALTH_CHECK_ENABLED = False
```

## How It Works

1. **Initial Startup**: On start, the monitor launches all configured services
2. **Process Tracking**: Tracks running processes for each service
3. **Hourly Restart Cycle**:
   - Kills all existing processes for each service
   - Waits for graceful shutdown
   - Starts fresh instances of each service
   - Logs the restart process
4. **Health Monitoring**: Continuously checks service health via TCP connections
5. **Graceful Shutdown**: Properly terminates all processes when stopped

## Logging

The monitor creates detailed logs in `pm2_monitor.log`:

```
2024-01-15 10:00:00 - INFO - PM2 Monitor started
2024-01-15 10:00:00 - INFO - Hourly restart enabled: True
2024-01-15 10:00:00 - INFO - Performing initial startup of all services...
2024-01-15 10:00:00 - INFO - Starting TWIFO Sharing from C:\Program Files\...
2024-01-15 10:00:00 - INFO - ✓ TWIFO Sharing restarted successfully (restart #1)
...
2024-01-15 11:00:00 - INFO - Hourly restart triggered (last restart: 3600s ago)
2024-01-15 11:00:00 - INFO - ============================================================
2024-01-15 11:00:00 - INFO - RESTARTING ALL SERVICES
2024-01-15 11:00:00 - INFO - ============================================================
```

## Service Management

### Adding a New Service

1. Add the service to `SERVICES` dictionary in `pm2_config.py`:
   ```python
   SERVICES["My New Service"] = r"C:\Path\To\my_service.bat"
   ```

2. Add health check port (if applicable):
   ```python
   PORTS["My New Service"] = ("127.0.0.1", 8080)
   ```

3. Restart the monitor

### Removing a Service

1. Remove the service from both `SERVICES` and `PORTS` dictionaries
2. Restart the monitor

### Modifying Service Paths

1. Update the path in the `SERVICES` dictionary
2. Restart the monitor

## Troubleshooting

### Service Won't Start
- Check that the batch file path is correct
- Verify the batch file exists and is executable
- Check the logs for specific error messages

### Process Not Being Killed
- The monitor uses process name matching to find processes
- Check `PROCESS_PATTERNS` in `pm2_config.py` for better process identification
- Some processes may require manual termination

### Health Checks Failing
- Verify that services are actually listening on the configured ports
- Check firewall settings
- Ensure services are running and accessible

### High Resource Usage
- Adjust `HEALTH_CHECK_INTERVAL` to reduce check frequency
- Consider disabling health monitoring if not needed
- Check individual service resource usage

## Advanced Features

### Custom Process Patterns
Modify `PROCESS_PATTERNS` in `pm2_config.py` to better identify processes:

```python
PROCESS_PATTERNS = {
    "My Service": ["myapp", "my-service", "node"],
}
```

### Performance Monitoring
Enable performance monitoring to restart services based on resource usage:

```python
PERFORMANCE_MONITORING = True
MEMORY_THRESHOLD = 1024  # MB
CPU_THRESHOLD = 80       # %
```

### Notifications
Configure notifications for service failures (future feature):

```python
NOTIFICATIONS_ENABLED = True
NOTIFICATION_EMAIL = "admin@example.com"
```

## File Structure

```
Manager/
├── pm2_monitor.py          # Main monitor script
├── pm2_config.py           # Configuration file
├── start_pm2_monitor.bat   # Windows batch file to start monitor
├── requirements.txt        # Python dependencies
├── pm2_monitor.log         # Log file (created when running)
└── PM2_MONITOR_README.md   # This documentation
```

## Requirements

- Python 3.8 or higher
- Windows operating system
- psutil library (installed via requirements.txt)

## License

This project is provided as-is for internal use. Modify as needed for your environment.
