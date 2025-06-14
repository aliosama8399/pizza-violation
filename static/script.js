document.addEventListener('DOMContentLoaded', () => {
    const violationCountElement = document.getElementById('violation-count');
    const fetchCountButton = document.getElementById('fetch-count');
    const processVideoButton = document.getElementById('process-video');
    const videoUploadInput = document.getElementById('video-upload');
    const framesContainer = document.getElementById('frames-container');
    let pollInterval;

    // Check if elements exist before adding event listeners
    if (fetchCountButton) {
        fetchCountButton.addEventListener('click', async function() {
            try {
                const response = await fetch('/violations/count');
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                const data = await response.json();
                if (violationCountElement) {
                    violationCountElement.textContent = data.violation_count;
                }
            } catch (error) {
                console.error('Error fetching violation count:', error);
                if (violationCountElement) {
                    violationCountElement.textContent = 'Error fetching count';
                }
            }
        });
    }

    if (processVideoButton) {
        processVideoButton.addEventListener('click', async () => {
            console.log('Process button clicked'); // Debug log

            if (!videoUploadInput.files.length) {
                alert('Please select a video file first.');
                return;
            }

            const file = videoUploadInput.files[0];
            console.log('Selected file:', file.name); // Debug log

            const formData = new FormData();
            formData.append('file', file);

            try {
                // Disable button and show processing state
                processVideoButton.disabled = true;
                processVideoButton.textContent = 'Processing...';
                violationCountElement.textContent = '0';
                framesContainer.innerHTML = '';

                console.log('Sending request to /process_video_upload'); // Debug log
                const response = await fetch('/process_video_upload', {
                    method: 'POST',
                    body: formData
                });

                console.log('Response received:', response.status); // Debug log
                const result = await response.json();
                
                if (!response.ok) {
                    throw new Error(result.error || 'Failed to process video');
                }

                violationCountElement.textContent = result.violation_count;
                await updateViolationFrames();
                
                alert('Video processing completed!');

            } catch (error) {
                console.error('Error:', error);
                alert('Error: ' + error.message);
            } finally {
                processVideoButton.disabled = false;
                processVideoButton.textContent = 'Process Video';
            }
        });
    }

    async function updateViolationFrames() {
        try {
            const response = await fetch('/violations/count');
            const data = await response.json();
            
            const framesContainer = document.getElementById('frames-container');
            const violationCount = document.getElementById('violation-count');
            
            violationCount.textContent = data.violation_count;
            
            if (data.frames && data.frames.length > 0) {
                framesContainer.innerHTML = data.frames
                    .map(frame => {
                        const [_, violationNum, frameNum, timestamp] = frame.split('_');
                        return `
                            <div class="violation-frame">
                                <img src="/violation_frames/${frame}?t=${Date.now()}" 
                                     alt="Violation ${violationNum}">
                                <div class="violation-info">
                                    <p>Violation #${violationNum}</p>
                                    <p>Frame: ${frameNum}</p>
                                    <p class="timestamp">Detected at: ${formatTimestamp(timestamp)}</p>
                                </div>
                            </div>
                        `;
                    })
                    .join('');
            }
        } catch (error) {
            console.error('Error updating violation frames:', error);
        }
    }

    function formatTimestamp(timestamp) {
        const date = new Date(parseInt(timestamp));
        return date.toLocaleString();
    }

    // Call updateViolationFrames every 2 seconds while processing
    let updateInterval;
    function startFrameUpdates() {
        updateViolationFrames();
        updateInterval = setInterval(updateViolationFrames, 2000);
    }

    function stopFrameUpdates() {
        if (updateInterval) {
            clearInterval(updateInterval);
        }
    }

    // Setup WebSocket connection for real-time updates
    const ws = new WebSocket(`ws://${window.location.host}/ws`);
    
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        
        // Update violation count
        document.getElementById('violation-count').textContent = data.violation_count;
        
        // Add new violation frame to container
        const framesContainer = document.getElementById('frames-container');
        const violationFrame = document.createElement('div');
        violationFrame.className = 'violation-frame new-violation';
        violationFrame.innerHTML = `
            <img src="/${data.frame_path}?t=${Date.now()}" alt="Violation frame">
            <div class="violation-info">
                <p>Frame: ${data.frame_number}</p>
                <p>Time: ${new Date(data.timestamp).toLocaleTimeString()}</p>
            </div>
        `;
        
        // Add to beginning of container
        framesContainer.insertBefore(violationFrame, framesContainer.firstChild);
        
        // Highlight new violation briefly
        setTimeout(() => {
            violationFrame.classList.remove('new-violation');
        }, 2000);
    };
});

async function updateViolationCount() {
    try {
        const response = await fetch('/violations/count');
        const data = await response.json();
        document.getElementById('violationCount').querySelector('span').textContent = data.violation_count;
    } catch (error) {
        console.error('Error fetching violation count:', error);
    }
}