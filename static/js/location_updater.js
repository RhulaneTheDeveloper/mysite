function sendLocationToServer(lat, lon) {
    fetch('/update_location', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({
            latitude: lat,
            longitude: lon
        })
    }).then(response => {
        if (!response.ok) {
            console.error("Failed to update location");
        }
    }).catch(err => console.error("Fetch error:", err));
}

function updateLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            position => {
                let lat = position.coords.latitude;
                let lon = position.coords.longitude;
                sendLocationToServer(lat, lon);
            },
            error => {
                console.error("Geolocation error:", error);
            },
            { enableHighAccuracy: true }
        );
    }
}

// Call every 60 seconds
setInterval(updateLocation, 6000);

// Call once on load
updateLocation();
