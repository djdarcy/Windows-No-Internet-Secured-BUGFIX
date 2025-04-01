# Wi-Fi Power Management Settings

## Overview

The NCSI Resolver includes Wi-Fi power management optimizations as part of its installation process. These settings help maintain stable network connections, which matters for reliable internet connectivity detection.

## What Power Management Settings Are Modified

When you install NCSI Resolver with Wi-Fi optimization enabled (the default), the following changes are made:

1. **Wireless Adapter Power Saving Mode**: Disabled
   - This prevents the Wi-Fi adapter from entering low-power states
   - Particularly important for Intel Wi-Fi adapters which often prioritize power saving over connection stability

2. **Roaming Aggressiveness**: Set to low (value 1)
   - Reduces frequency of scanning for new access points
   - Helps maintain stable connections to current access point

3. **Preferred Band**: Set to 5GHz when available
   - 5GHz connections are typically more stable and less congested
   - Provides better performance for most modern networks

## Why These Settings Matter

Modern Windows devices, especially laptops, often use aggressive power saving features to extend battery life. While beneficial for mobility, these features can cause problems for network connectivity:

1. **Intermittent Disconnections**: Power saving mode can cause the Wi-Fi adapter to periodically sleep, resulting in brief disconnections

2. **NCSI Status Fluctuations**: These brief disconnections trigger Windows to reset its Network Connectivity Status Indicator

3. **Application Connectivity Issues**: Applications that rely on NCSI may repeatedly disconnect and reconnect, causing synchronization problems

By optimizing power settings, NCSI Resolver ensures that your Wi-Fi connection remains stable, which helps maintain accurate connectivity status in Windows.

## Disabling Wi-Fi Optimization

If you prefer to manage power settings yourself or don't want to modify these settings:

1. During installation, use the `--no-wifi` flag:
   ```
   installer.py --install --no-wifi
   ```

2. Or edit the registry keys manually:
   - Navigate to: `Computer\HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}\00XX`
   - Look for your Wi-Fi adapter's subkey
   - Adjust "PwrManagement" and related values

## Reverting Changes

When you uninstall NCSI Resolver, these power settings are not automatically reverted, as they may have been beneficial to your system's network stability.

To manually revert to default power settings:

1. Open Device Manager
2. Locate your wireless network adapter
3. Right-click and select Properties
4. Go to the Power Management tab
5. Re-enable "Allow the computer to turn off this device to save power"
