#!/bin/bash

# protonvpn-cli ks --off && \
# protonvpn-cli ns --off && \
# protonvpn-cli connect -f
# while true
# do
#     protonvpn-cli disconnect && \
#     protonvpn-cli connect -f && \
#     protonvpn-cli ks --on && \
#     protonvpn-cli ns --ads-malware

#     sleep 1800
# done

# # ----------------------------

# protonvpn-cli connect -f && \
# protonvpn-cli ks --on && \
# protonvpn-cli ns --ads-malware

# ----------------------------

# protonvpn-cli disconnect

# protonvpn-cli ks --off && \
# protonvpn-cli ns --off

# protonvpn-cli connect -f && \
# protonvpn-cli ks --on && \
# protonvpn-cli ns --ads-malware

# while true
# do
#     #protonvpn-cli disconnect
#     protonvpn-cli connect -f

#     #sleep 1800
#     #sleep 3600
#     #sleep 7200
#     sleep 10800
#     #sleep 60
# done

# ----------------------------

#!/bin/bash

# Function to fetch the DBUS_SESSION_BUS_ADDRESS
# get_dbus_session() {
#     if [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then
#         DBUS_SESSION_BUS_ADDRESS=$(grep -z DBUS_SESSION_BUS_ADDRESS /proc/$(pgrep -u $USER gnome-session)*/environ 2>/dev/null | cut -d= -f2-)
#         if [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then
#             echo "DBUS_SESSION_BUS_ADDRESS not found."
#             return 1
#         else
#             export DBUS_SESSION_BUS_ADDRESS
#             echo "DBUS_SESSION_BUS_ADDRESS set to $DBUS_SESSION_BUS_ADDRESS"
#         fi
#     fi
#     return 0
# }

# Call the function to set DBUS_SESSION_BUS_ADDRESS
# get_dbus_session

# Function to disconnect and turn off kill switch and DNS protection
disconnect_vpn() {
    echo "Disconnecting VPN and turning off kill switch and DNS protection..."
    protonvpn-cli disconnect
    protonvpn-cli ks --off && \
    protonvpn-cli ns --off
    echo "VPN disconnected."
}

# Function to connect to VPN and enable kill switch and DNS protection
connect_vpn() {
    echo "Connecting to VPN with kill switch and DNS protection..."
    protonvpn-cli connect -f && \
    protonvpn-cli ks --on && \
    protonvpn-cli ns --ads-malware
    echo "VPN connected with kill switch and DNS protection enabled."
}

# Function to check connection status
check_connection() {
    # Capture the output of the status command
    vpn_status=$(protonvpn-cli status)

    # Check if the output contains "No active Proton VPN connection"
    if echo "$vpn_status" | grep -q "No active Proton VPN connection"; then
        echo "VPN is disconnected. Reconnecting..."
        return 1
    fi

    # Alternatively, check for the "IP" field in the
    # status output to verify a connected state
    if echo "$vpn_status" | grep -q "IP:"; then
        echo "VPN is connected."
        return 0
    else
        echo "Unexpected status. Assuming VPN is disconnected."
        return 1
    fi
}

cycle_vpn() {
    protonvpn-cli disconnect
    protonvpn-cli connect -f
}

# Initial disconnect and connect to start fresh
disconnect_vpn
connect_vpn

# Infinite loop to manage connection check and timed reconnection
# reconnect_interval=3600  # 1 hour in seconds
# reconnect_interval=7200  # 2 hours in seconds
# reconnect_interval=10800  # 3 hours in seconds
reconnect_interval=259200 # 3 days in seconds

elapsed_time=0
while true
do
    # Check connection every minute
    check_connection
    if [ $? -ne 0 ]; then
        # If disconnected, reconnect and reset elapsed time
        cycle_vpn
        elapsed_time=0  # Reset elapsed time after reconnection
    fi

    # Sleep for 1 hour
    sleep 60m

    # Increment elapsed time
    elapsed_time=$((elapsed_time + 60))

    # Reconnect every 3 hours (10800 seconds)
    if [ $elapsed_time -ge $reconnect_interval ]; then
        cycle_vpn
        elapsed_time=0  # Reset the elapsed time after reconnection
    fi
done
