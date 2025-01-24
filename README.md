# Kronoterm Integration for Home Assistant

## Overview
This custom integration provides support for Kronoterm heat pumps in Home Assistant. It fetches and displays various sensor data and operational statuses from the Kronoterm API, offering users valuable insights into their heat pump's performance and status.

Tested with: 
- Hydro S + Adapt 0416-K3 HT / HK 3F
- Hydro C 2 + Adapt 0312-K3 HT / HK 1F

## Features
- Integration with Kronoterm's API to fetch sensor and binary sensor data.
- Provides detailed information such as temperatures, pressures, energy consumption, and operational statuses.
- Configurable update intervals for main and auxiliary data.

![integration](https://github.com/Favio25/kronoterm-homeassistant/blob/main/images/integration.png)
![hp_load](https://github.com/Favio25/kronoterm-homeassistant/blob/main/images/HP_load.png)
![outside_temp](https://github.com/Favio25/kronoterm-homeassistant/blob/main/images/Outside_temp.png)

## Installation

### Install via HACS
1. **Add the Repository**  
   Open HACS in your Home Assistant interface and navigate to **Integrations**. Click the three dots in the top right corner and select **Custom Repositories**. Add this repository's URL and select **Integration** as the category.

2. **Install the Integration**  
   After adding the repository, search for "Kronoterm" in HACS under **Integrations**. Click on it and select **Install**.

3. **Restart Home Assistant**  
   Restart Home Assistant to recognize the new integration.

4. **Add the Integration**  
   Go to **Settings > Devices & Services** in Home Assistant. Click the "Add Integration" button and search for "Kronoterm." Follow the prompts to configure the integration with your Kronoterm credentials.

### Manual Installation
1. **Download the Integration**  
   Clone or download the repository containing this integration and place the folder in your Home Assistant `custom_components` directory. If the `custom_components` folder doesn't exist, create it in your Home Assistant configuration directory.

   ```
   <config_dir>/custom_components/kronoterm/
   ```

2. **Restart Home Assistant**  
   Restart Home Assistant to recognize the new integration.

3. **Add the Integration**  
   Go to **Settings > Devices & Services** in Home Assistant. Click the "Add Integration" button and search for "Kronoterm." Follow the prompts to configure the integration with your Kronoterm credentials.
   ![setup](https://github.com/Favio25/kronoterm-homeassistant/blob/main/images/Setup.png)

5. **Customize Update Intervals** (Optional)  
   Update intervals can be modified by specifying the `scan_interval` parameter in the configuration.

## Troubleshooting
- **Integration Not Showing**: Ensure the integration is placed in the correct directory and Home Assistant is restarted.
- **Data Fetch Errors**: Check your internet connection and verify your Kronoterm credentials in the configuration.
- **API Limitations**: If data isn't refreshing as expected, verify the update intervals and API connectivity.

## Contribution
Contributions are welcome! Submit pull requests or open issues for bugs, enhancements, or feature requests.

---
