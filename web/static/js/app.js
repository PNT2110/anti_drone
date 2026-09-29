document.addEventListener('DOMContentLoaded', () => {
    // UI Elements
    const modelSelect = document.getElementById('model-select');
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    // Stats Elements
    const statTime = document.getElementById('stat-time');
    const statFps = document.getElementById('stat-fps');
    const statCount = document.getElementById('stat-count');
    const statConf = document.getElementById('stat-conf');
    
    // Video Upload Elements
    const uploadZone = document.getElementById('upload-zone');
    const videoInput = document.getElementById('video-input');
    const videoResultContainer = document.getElementById('video-result-container');
    const videoStream = document.getElementById('video-stream');
    const downloadBtn = document.getElementById('download-btn');
    let currentTaskId = null;
    let statsInterval = null;
    
    // Webcam Elements
    const webcamVideo = document.getElementById('webcam-video');
    const webcamCanvas = document.getElementById('webcam-canvas');
    const ctx = webcamCanvas.getContext('2d');
    const startWebcamBtn = document.getElementById('start-webcam');
    const stopWebcamBtn = document.getElementById('stop-webcam');
    let ws = null;
    let isWebcamRunning = false;
    let stream = null;
    let lastFrameTime = performance.now();
    let frameCount = 0;

    // Load Models
    fetch('/api/models')
        .then(res => res.json())
        .then(data => {
            modelSelect.innerHTML = '';
            data.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.name;
                option.textContent = model.display_name || model.name;
                modelSelect.appendChild(option);
            });
        })
        .catch(err => console.error('Error loading models:', err));

    // Handle Model Switch
    modelSelect.addEventListener('change', (e) => {
        const formData = new FormData();
        formData.append('model_name', e.target.value);
        fetch('/api/models/switch', {
            method: 'POST',
            body: formData
        }).then(res => res.json())
          .then(data => console.log('Model switched:', data));
    });

    // Tab Switching
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            document.getElementById(btn.dataset.tab).classList.add('active');
            
            if (btn.dataset.tab === 'video-tab' && isWebcamRunning) {
                stopWebcam();
            }
        });
    });

    // --- Video Upload Logic ---
    uploadZone.addEventListener('click', () => videoInput.click());
    
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });
    
    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });
    
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            handleVideoUpload(e.dataTransfer.files[0]);
        }
    });
    
    videoInput.addEventListener('change', (e) => {
        if (e.target.files.length) {
            handleVideoUpload(e.target.files[0]);
        }
    });

    function handleVideoUpload(file) {
        if (!file.type.startsWith('video/')) {
            alert('Vui lòng chọn file video!');
            return;
        }
        
        uploadZone.style.display = 'none';
        videoResultContainer.style.display = 'flex';
        videoStream.src = '';
        downloadBtn.disabled = true;
        
        const formData = new FormData();
        formData.append('file', file);
        
        fetch('/api/video/upload', {
            method: 'POST',
            body: formData
        })
        .then(res => res.json())
        .then(data => {
            currentTaskId = data.task_id;
            videoStream.src = `/api/video/stream/${currentTaskId}`;
            
            if (statsInterval) clearInterval(statsInterval);
            statsInterval = setInterval(updateVideoStats, 1000);
            
            // Assume completion after stream ends or polling indicates completion
            // Simplified: enable download button after some time or check status
            setTimeout(() => {
                downloadBtn.disabled = false;
            }, 5000); // For demo, ideally poll status endpoint
        });
    }
    
    function updateVideoStats() {
        if (!currentTaskId) return;
        fetch(`/api/video/stats/${currentTaskId}`)
            .then(res => res.json())
            .then(stats => {
                if(stats.inference_time_ms !== undefined) updateStatsDisplay(stats);
            });
    }

    downloadBtn.addEventListener('click', () => {
        if (currentTaskId) {
            window.location.href = `/api/video/download/${currentTaskId}`;
        }
    });

    // --- Webcam Logic ---
    startWebcamBtn.addEventListener('click', startWebcam);
    stopWebcamBtn.addEventListener('click', stopWebcam);

    async function startWebcam() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
            webcamVideo.srcObject = stream;
            
            webcamVideo.onloadedmetadata = () => {
                webcamCanvas.width = webcamVideo.videoWidth;
                webcamCanvas.height = webcamVideo.videoHeight;
                isWebcamRunning = true;
                startWebcamBtn.disabled = true;
                stopWebcamBtn.disabled = false;
                
                connectWebSocket();
            };
        } catch (err) {
            console.error('Error accessing webcam:', err);
            alert('Không thể truy cập camera!');
        }
    }

    function stopWebcam() {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
        }
        isWebcamRunning = false;
        if (ws) {
            ws.close();
        }
        startWebcamBtn.disabled = false;
        stopWebcamBtn.disabled = true;
    }

    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${protocol}//${window.location.host}/ws/webcam`);
        
        ws.onopen = () => {
            sendFrame();
        };
        
        ws.onmessage = (event) => {
            if (!isWebcamRunning) return;
            const data = JSON.parse(event.data);
            
            // Draw image on canvas
            const img = new Image();
            img.onload = () => {
                ctx.drawImage(img, 0, 0, webcamCanvas.width, webcamCanvas.height);
                
                // Calculate FPS
                const now = performance.now();
                const delta = now - lastFrameTime;
                lastFrameTime = now;
                const currentFps = 1000 / delta;
                
                // Update stats
                data.stats.fps = currentFps;
                updateStatsDisplay(data.stats);
                
                // Request next frame
                requestAnimationFrame(sendFrame);
            };
            img.src = data.image;
        };
        
        ws.onclose = () => {
            if (isWebcamRunning) {
                setTimeout(connectWebSocket, 1000); // Reconnect
            }
        };
    }

    function sendFrame() {
        if (!isWebcamRunning || ws.readyState !== WebSocket.OPEN) return;
        
        // Draw video frame to canvas
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = webcamVideo.videoWidth;
        tempCanvas.height = webcamVideo.videoHeight;
        tempCanvas.getContext('2d').drawImage(webcamVideo, 0, 0);
        
        // Get base64 jpeg
        const dataURL = tempCanvas.toDataURL('image/jpeg', 0.8);
        ws.send(dataURL);
    }

    function updateStatsDisplay(stats) {
        if(stats.inference_time_ms !== undefined) statTime.textContent = stats.inference_time_ms.toFixed(1) + ' ms';
        if(stats.fps !== undefined) statFps.textContent = stats.fps.toFixed(1);
        if(stats.total_detections !== undefined) statCount.textContent = stats.total_detections;
        if(stats.avg_confidence !== undefined) statConf.textContent = (stats.avg_confidence * 100).toFixed(1) + '%';
    }
});
