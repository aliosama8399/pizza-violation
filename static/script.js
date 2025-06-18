document.addEventListener('DOMContentLoaded', () => {
    const processVideoButton = document.getElementById('process-video');
    const videoUploadInput = document.getElementById('video-upload');

    if (processVideoButton) {
        processVideoButton.addEventListener('click', async () => {
            if (!videoUploadInput.files.length) {
                alert('Please select a video file first.');
                return;
            }
            const file = videoUploadInput.files[0];
            const formData = new FormData();
            formData.append('file', file);

            processVideoButton.disabled = true;
            processVideoButton.textContent = 'Processing...';

            try {
                const response = await fetch('/process_video_upload', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || 'Failed to process video');
                alert(result.message);
            } catch (error) {
                console.error('Error:', error);
                alert('Error: ' + error.message);
            } finally {
                processVideoButton.disabled = false;
                processVideoButton.textContent = 'Process Video';
            }
        });
    }

    const ws = new WebSocket(`ws://${window.location.host}/ws`);
    ws.onopen = () => console.log("WebSocket connection established.");
    ws.onclose = () => console.log("WebSocket connection closed.");
    ws.onerror = (error) => console.error("WebSocket error:", error);
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        console.log("Received event:", data);

        if (data.type === 'video_ready') {
            displayVideoPlayer(data);
        } else if (data.type === 'violation') {
            addViolationEntry(data);
        }
    };
});

function displayVideoPlayer(data) {
    const container = document.getElementById('processed-video-container');
    if (!container) return;
    
    container.innerHTML = `
        <h2>Processed Video: ${data.video_name}</h2>
        <video src="${data.video_url}" controls autoplay muted style="width: 100%; border-radius: 8px;"></video>
    `;
}

function addViolationEntry(violation) {
    const container = document.getElementById('violations-log-container');
    const countElement = document.getElementById('violation-count');
    if (!container || !countElement) return;

    const entry = document.createElement('div');
    entry.className = 'violation-entry new-violation';

    const timestamp = new Date(violation.timestamp).toLocaleString();
    const bbox = violation.bbox ? violation.bbox.join(', ') : 'N/A';

    entry.innerHTML = `
        <img src="${violation.violation_frame_path}?t=${Date.now()}" alt="Violation Frame">
        <div class="violation-details">
            <p><strong>Violation Type:</strong> ${violation.violation_type}</p>
            <p><strong>Frame:</strong> ${violation.frame_number}</p>
            <p><strong>Bounding Box:</strong> [${bbox}]</p>
            <p><strong>Time:</strong> ${timestamp}</p>
        </div>
    `;
    
    container.prepend(entry);
    
    // Update total count
    const currentCount = parseInt(countElement.textContent);
    countElement.textContent = currentCount + 1;

    setTimeout(() => entry.classList.remove('new-violation'), 2000);
}