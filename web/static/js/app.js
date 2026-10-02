document.addEventListener('DOMContentLoaded', () => {
    const $ = (id) => document.getElementById(id);
    const modelSelect = $('model-select'), activeModelName = $('active-model-name'), modelState = $('model-state');
    const systemStatus = $('system-status-text'), tabBtns = document.querySelectorAll('.tab-btn'), tabContents = document.querySelectorAll('.tab-content');
    const uploadZone = $('upload-zone'), videoInput = $('video-input'), videoResultContainer = $('video-result-container');
    const videoStream = $('video-stream'), downloadBtn = $('download-btn'), resetBtn = $('reset-btn');
    const progressBar = $('progress-bar'), progressText = $('progress-text'), progressPercent = $('progress-percent'), processingBadge = $('processing-badge');
    const webcamVideo = $('webcam-video'), webcamCanvas = $('webcam-canvas'), webcamPlaceholder = $('webcam-placeholder');
    const ctx = webcamCanvas.getContext('2d'), startWebcamBtn = $('start-webcam'), stopWebcamBtn = $('stop-webcam');
    const captureCanvas = document.createElement('canvas'), captureCtx = captureCanvas.getContext('2d');
    let currentTaskId = null, statsInterval = null, activeModel = null, ws = null, stream = null, isWebcamRunning = false, lastFrameTime = performance.now();

    function setStatus(text, state = 'ready') { systemStatus.textContent = text; document.body.dataset.state = state; if (state === 'processing') modelState.textContent = 'PROCESSING'; }
    function notify(message, type = 'info') {
        const old = document.querySelector('.toast'); if (old) old.remove();
        const toast = document.createElement('div'); toast.className = 'toast toast-' + type;
        const icon = document.createElement('i'); icon.className = 'fa-solid ' + (type === 'error' ? 'fa-circle-exclamation' : 'fa-circle-info');
        const text = document.createElement('span'); text.textContent = message; toast.append(icon, text);
        document.body.appendChild(toast); setTimeout(() => toast.remove(), 4200);
    }
    async function errorMessage(response, fallback) {
        try { const data = await response.json(); return data.message || data.error || fallback; } catch (error) { return fallback; }
    }
    function updateStatsDisplay(stats = {}) {
        if (stats.inference_time_ms !== undefined) $('stat-time').textContent = Number(stats.inference_time_ms).toFixed(1) + ' ms';
        if (stats.fps !== undefined) $('stat-fps').textContent = Number(stats.fps).toFixed(1);
        if (stats.total_detections !== undefined) $('stat-count').textContent = stats.total_detections;
        if (stats.avg_confidence !== undefined) $('stat-conf').textContent = (Number(stats.avg_confidence) * 100).toFixed(1) + '%';
        if ($('track-ids')) {
            const ids = (stats.track_ids || []).map((id) => `ID ${id}`);
            $('track-ids').textContent = ids.length ? ids.join(' · ') : '—';
        }
    }
    async function loadModels() {
        try {
            const response = await fetch('/api/models'); if (!response.ok) throw new Error('Không thể tải danh sách mô hình');
            const data = await response.json(); modelSelect.innerHTML = '';
            (data.models || []).forEach((model) => { const option = document.createElement('option'); option.value = model.name; option.textContent = model.display_name || model.name; option.selected = model.name === data.active; modelSelect.appendChild(option); });
            const active = data.active || (data.models && data.models[0] && data.models[0].name) || 'Chưa chọn mô hình'; activeModel = data.active || null; activeModelName.textContent = active; setStatus('Hệ thống sẵn sàng');
        } catch (error) { activeModelName.textContent = 'Không khả dụng'; setStatus('Không kết nối được backend', 'error'); notify(error.message, 'error'); }
    }
    modelSelect.addEventListener('change', async (event) => {
        const modelName = event.target.value; if (!modelName) return; activeModelName.textContent = modelName; modelState.textContent = 'SWITCHING';
        try { const body = new FormData(); body.append('model_name', modelName); const response = await fetch('/api/models/switch', { method: 'POST', body }); if (!response.ok) throw new Error(await errorMessage(response, 'Không thể chuyển mô hình')); activeModel = modelName; modelState.textContent = 'READY'; notify('Đã chuyển sang ' + modelName); }
        catch (error) { modelState.textContent = 'ERROR'; if (activeModel) { modelSelect.value = activeModel; activeModelName.textContent = activeModel; } notify(error.message, 'error'); }
    });
    tabBtns.forEach((button) => button.addEventListener('click', () => {
        tabBtns.forEach((item) => { item.classList.remove('active'); item.setAttribute('aria-selected', 'false'); }); tabContents.forEach((item) => item.classList.remove('active'));
        button.classList.add('active'); button.setAttribute('aria-selected', 'true'); $(button.dataset.tab).classList.add('active'); if (button.dataset.tab === 'video-tab' && isWebcamRunning) stopWebcam();
    }));
    function openFilePicker() { videoInput.click(); }
    uploadZone.addEventListener('click', openFilePicker);
    uploadZone.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openFilePicker(); } });
    uploadZone.addEventListener('dragover', (event) => { event.preventDefault(); uploadZone.classList.add('dragover'); });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
    uploadZone.addEventListener('drop', (event) => { event.preventDefault(); uploadZone.classList.remove('dragover'); if (event.dataTransfer.files.length) handleVideoUpload(event.dataTransfer.files[0]); });
    videoInput.addEventListener('change', (event) => { if (event.target.files.length) handleVideoUpload(event.target.files[0]); });
    async function handleVideoUpload(file) {
        if (!file.type.startsWith('video/')) { notify('Vui lòng chọn một tệp video hợp lệ.', 'error'); return; }
        uploadZone.style.display = 'none'; videoResultContainer.style.display = 'flex'; videoStream.src = ''; downloadBtn.disabled = true; progressBar.style.width = '0%'; progressPercent.textContent = '0%';
        progressText.textContent = 'Đang tải video lên...'; processingBadge.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> ĐANG KHỞI TẠO'; setStatus('Đang tiếp nhận video', 'processing');
        try { const body = new FormData(); body.append('file', file); const response = await fetch('/api/video/upload', { method: 'POST', body }); if (!response.ok) throw new Error(await errorMessage(response, 'Upload video thất bại')); const data = await response.json(); currentTaskId = data.task_id; videoStream.src = '/api/video/stream/' + currentTaskId; if (statsInterval) clearInterval(statsInterval); statsInterval = setInterval(updateVideoStats, 700); notify('Đã nhận ' + file.name); updateVideoStats(); }
        catch (error) { notify(error.message, 'error'); resetVideo(); }
    }
    async function updateVideoStats() {
        if (!currentTaskId) return;
        try {
            const response = await fetch('/api/video/stats/' + currentTaskId);
            if (!response.ok) { if (statsInterval) clearInterval(statsInterval); processingBadge.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> LỖI'; setStatus('Không tìm thấy tác vụ video', 'error'); return; }
            const stats = await response.json();
            const percent = Math.max(0, Math.min(100, Number(stats.progress || (stats.total_frames ? stats.processed_frames / stats.total_frames * 100 : 0))));
            progressBar.style.width = percent + '%'; progressPercent.textContent = percent.toFixed(0) + '%';
            progressText.textContent = stats.status === 'completed' ? 'Phân tích hoàn tất' : stats.status === 'error' ? 'Phân tích gặp lỗi' : 'Đang xử lý · ' + (stats.processed_frames || 0) + ' / ' + (stats.total_frames || '—') + ' frames';
            updateStatsDisplay(stats);
            if (stats.status === 'completed') { downloadBtn.disabled = false; processingBadge.innerHTML = '<i class="fa-solid fa-circle-check"></i> HOÀN TẤT'; setStatus('Phân tích hoàn tất'); if (statsInterval) clearInterval(statsInterval); }
            if (stats.status === 'error') { processingBadge.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> LỖI'; setStatus('Phân tích thất bại', 'error'); if (statsInterval) clearInterval(statsInterval); if (stats.message) notify(stats.message, 'error'); }
        } catch (error) { console.warn('Stats error:', error); }
    }
    downloadBtn.addEventListener('click', () => { if (currentTaskId) window.location.href = '/api/video/download/' + currentTaskId; });
    resetBtn.addEventListener('click', resetVideo);
    function resetVideo() { if (statsInterval) clearInterval(statsInterval); currentTaskId = null; videoInput.value = ''; videoStream.src = ''; videoResultContainer.style.display = 'none'; uploadZone.style.display = 'flex'; progressBar.style.width = '0%'; progressPercent.textContent = '0%'; progressText.textContent = 'Đang khởi tạo...'; setStatus('Hệ thống sẵn sàng'); updateStatsDisplay({ fps: 0, inference_time_ms: 0, total_detections: 0, avg_confidence: 0 }); }
    startWebcamBtn.addEventListener('click', startWebcam); stopWebcamBtn.addEventListener('click', stopWebcam);
    async function startWebcam() {
        if (!window.isSecureContext && !['localhost', '127.0.0.1'].includes(window.location.hostname)) {
            notify('Chrome chỉ cho camera trên HTTPS hoặc localhost. Mở link HTTPS của tunnel để dùng camera máy bạn.', 'error');
            return;
        }
        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30, max: 30 } }, audio: false });
            webcamVideo.srcObject = stream;
            webcamVideo.onloadedmetadata = () => {
                webcamCanvas.width = webcamVideo.videoWidth || 1280;
                webcamCanvas.height = webcamVideo.videoHeight || 720;
                const scale = Math.min(1, 640 / webcamCanvas.width);
                captureCanvas.width = Math.max(1, Math.round(webcamCanvas.width * scale));
                captureCanvas.height = Math.max(1, Math.round(webcamCanvas.height * scale));
                webcamPlaceholder.style.display = 'none';
                isWebcamRunning = true;
                startWebcamBtn.disabled = true;
                stopWebcamBtn.disabled = false;
                setStatus('Camera máy bạn đang hoạt động', 'processing');
                connectWebSocket();
            };
        } catch (error) {
            notify('Không thể truy cập camera máy bạn. Hãy bấm Allow quyền Camera cho link HTTPS.', 'error');
        }
    }
    function stopWebcam() { if (stream) stream.getTracks().forEach((track) => track.stop()); stream = null; isWebcamRunning = false; if (ws) ws.close(); ws = null; webcamVideo.srcObject = null; webcamPlaceholder.style.display = 'flex'; startWebcamBtn.disabled = false; stopWebcamBtn.disabled = true; setStatus('Hệ thống sẵn sàng'); updateStatsDisplay({ fps: 0, inference_time_ms: 0, total_detections: 0, avg_confidence: 0, track_ids: [] }); }
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(protocol + '//' + window.location.host + '/ws/webcam');
        ws.onopen = () => sendFrame();
        ws.onmessage = (event) => {
            if (!isWebcamRunning) return;
            const data = JSON.parse(event.data);
            if (data.error) { notify(data.error, 'error'); stopWebcam(); return; }
            const image = new Image();
            image.onload = () => {
                if (!webcamCanvas.width || !webcamCanvas.height) { webcamCanvas.width = image.naturalWidth; webcamCanvas.height = image.naturalHeight; }
                ctx.drawImage(image, 0, 0, webcamCanvas.width, webcamCanvas.height);
                const now = performance.now();
                data.stats.fps = 1000 / Math.max(now - lastFrameTime, 1);
                lastFrameTime = now;
                updateStatsDisplay(data.stats);
                setStatus('Camera máy bạn đang hoạt động', 'processing');
                requestAnimationFrame(sendFrame);
            };
            image.src = data.image;
        };
        ws.onerror = () => notify('Không kết nối được camera server.', 'error');
        ws.onclose = () => { if (isWebcamRunning) setTimeout(connectWebSocket, 1000); };
    }
    function sendFrame() {
        if (!isWebcamRunning || !ws || ws.readyState !== WebSocket.OPEN) return;
        captureCtx.drawImage(webcamVideo, 0, 0, captureCanvas.width, captureCanvas.height);
        ws.send(captureCanvas.toDataURL('image/jpeg', 0.72));
    }
    loadModels();
});
