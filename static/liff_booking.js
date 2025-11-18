// LIFF 訂票頁面邏輯
let liffId = null;
let lineUserId = null;
let flightData = null;
let selectedCabin = null;
let selectedCabinPrice = 0;
let selectedSeats = [];
let currentStep = 1;

// 費用常數（與 ticket_service.py 一致）
const fees = {
    airportTax: 500,
    fuelSurcharge: 800,
    serviceFee: 200
};

// 艙等價格（假票價）
const cabinPrices = {
    economy: 5000,
    business: 12500,
    first: 20000
};

// ===== LIFF 初始化 =====
async function initializeLIFF() {
    try {
        // 從後端取得 LIFF ID
        const configResponse = await fetch('/api/liff/config');
        const config = await configResponse.json();
        liffId = config.liff_id;

        if (!liffId || liffId.includes('請在')) {
            alert('LIFF 尚未設定，請聯絡管理員');
            return;
        }

        // 初始化 LIFF
        await liff.init({ liffId: liffId });

        if (!liff.isLoggedIn()) {
            liff.login();
            return;
        }

        // 取得 LINE 使用者資訊
        const profile = await liff.getProfile();
        lineUserId = profile.userId;

        // 從 URL 參數取得 flight_id（LIFF 會把參數包在 liff.state 裡）
        let flightId = null;

        // 方法 1：從 liff.state 取得（LIFF 會自動處理）
        const urlParams = new URLSearchParams(window.location.search);
        const liffState = urlParams.get('liff.state');

        if (liffState) {
            // liff.state 格式：?flight_id=XXX 或 flight_id=XXX
            const stateParams = new URLSearchParams(liffState.startsWith('?') ? liffState.substring(1) : liffState);
            flightId = stateParams.get('flight_id');
        }

        // 方法 2：直接從 URL 參數取得（備用）
        if (!flightId) {
            flightId = urlParams.get('flight_id');
        }

        console.log('[DEBUG] liffState:', liffState);
        console.log('[DEBUG] flightId:', flightId);

        if (!flightId) {
            alert('缺少航班資訊');
            return;
        }

        // 載入航班資訊
        await loadFlightData(flightId);

        // 隱藏 loading，顯示主內容
        document.getElementById('loading').style.display = 'none';
        document.getElementById('main-content').style.display = 'block';

        // 初始化艙等選項
        initializeCabinOptions();

    } catch (error) {
        console.error('LIFF 初始化失敗:', error);
        alert('載入失敗，請稍後再試');
    }
}

// ===== 載入航班資訊 =====
async function loadFlightData(flightId) {
    try {
        console.log('[DEBUG] 載入航班資訊，flight_id:', flightId);
        const response = await fetch(`/api/flight/${flightId}`);
        const result = await response.json();

        console.log('[DEBUG] API 回應:', result);

        if (!result.success) {
            throw new Error(result.message || '載入航班資訊失敗');
        }

        flightData = result.data;
        console.log('[DEBUG] 航班資料:', flightData);
        displayFlightInfo();

    } catch (error) {
        console.error('載入航班資訊失敗:', error);
        alert('載入航班資訊失敗: ' + error.message);
    }
}

// ===== 顯示航班資訊 =====
function displayFlightInfo() {
    const container = document.getElementById('flight-info');
    container.innerHTML = `
        <div class="d-flex align-items-center mb-3">
            <div class="me-3">
                <h6 class="mb-0 fw-bold text-primary">${flightData.Airline_Name_ZH || '航空公司'}</h6>
                <span class="badge bg-secondary">${flightData.No || 'N/A'}</span>
            </div>
        </div>
        <div class="row">
            <div class="col-5 text-center">
                <div class="text-primary fw-bold">出發</div>
                <h5 class="fw-bold">${formatTime(flightData.D_Time)}</h5>
                <small class="text-muted">${flightData.D_Airport_Name_ZH || ''}</small>
            </div>
            <div class="col-2 text-center">
                <i class="fas fa-plane text-primary"></i>
            </div>
            <div class="col-5 text-center">
                <div class="text-primary fw-bold">抵達</div>
                <h5 class="fw-bold">${formatTime(flightData.A_Time)}</h5>
                <small class="text-muted">${flightData.A_Airport_Name_ZH || ''}</small>
            </div>
        </div>
    `;
}

// ===== 初始化艙等選項 =====
function initializeCabinOptions() {
    const container = document.getElementById('cabin-options');
    const cabins = [
        { id: 'economy', name: '經濟艙', icon: 'fa-couch', price: cabinPrices.economy },
        { id: 'business', name: '商務艙', icon: 'fa-briefcase', price: cabinPrices.business },
        { id: 'first', name: '頭等艙', icon: 'fa-crown', price: cabinPrices.first }
    ];

    container.innerHTML = cabins.map(cabin => `
        <div class="cabin-option" data-cabin="${cabin.id}" onclick="selectCabin('${cabin.id}', ${cabin.price})">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <i class="fas ${cabin.icon} text-primary me-2"></i>
                    <span class="fw-bold">${cabin.name}</span>
                </div>
                <div class="text-primary fw-bold">NT$ ${cabin.price.toLocaleString()}</div>
            </div>
        </div>
    `).join('');
}

// ===== 選擇艙等 =====
function selectCabin(cabin, price) {
    selectedCabin = cabin;
    selectedCabinPrice = price;
    
    // 更新 UI
    document.querySelectorAll('.cabin-option').forEach(el => {
        el.classList.remove('selected');
    });
    document.querySelector(`[data-cabin="${cabin}"]`).classList.add('selected');
}

// ===== 格式化時間 =====
function formatTime(timeStr) {
    if (!timeStr) return 'N/A';
    const date = new Date(timeStr);
    return date.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' });
}

// ===== 步驟切換 =====
function nextStep(step) {
    if (step === 2 && !selectedCabin) {
        alert('請先選擇艙等');
        return;
    }
    if (step === 3 && selectedSeats.length === 0) {
        alert('請先選擇座位');
        return;
    }

    // 隱藏當前步驟
    document.getElementById(`step-${currentStep}`).style.display = 'none';
    
    // 更新步驟指示器
    document.querySelector(`[data-step="${currentStep}"]`).classList.remove('active');
    document.querySelector(`[data-step="${currentStep}"]`).classList.add('completed');
    document.querySelector(`[data-step="${step}"]`).classList.add('active');
    
    // 顯示下一步驟
    document.getElementById(`step-${step}`).style.display = 'block';
    currentStep = step;

    // 初始化步驟內容
    if (step === 2) initializeSeatMap();
    if (step === 3) initializePassengerForms();
    if (step === 4) initializePaymentForm();
}

function prevStep(step) {
    document.getElementById(`step-${currentStep}`).style.display = 'none';
    document.querySelector(`[data-step="${currentStep}"]`).classList.remove('active');
    document.querySelector(`[data-step="${step}"]`).classList.remove('completed');
    document.querySelector(`[data-step="${step}"]`).classList.add('active');
    document.getElementById(`step-${step}`).style.display = 'block';
    currentStep = step;
}

// ===== 初始化座位圖 =====
function initializeSeatMap() {
    const container = document.getElementById('seat-map');
    const rows = 10; // 10排座位
    const cols = 6;  // 6個座位（A-F）
    const letters = ['A', 'B', 'C', 'D', 'E', 'F'];

    let html = '';
    for (let row = 1; row <= rows; row++) {
        for (let col = 0; col < cols; col++) {
            const seatId = `${row}${letters[col]}`;
            // 隨機產生已佔用座位（模擬真實情況）
            const isOccupied = Math.random() < 0.3;
            const occupiedClass = isOccupied ? 'occupied' : '';

            html += `
                <div class="seat ${occupiedClass}"
                     data-seat="${seatId}"
                     onclick="toggleSeat('${seatId}', ${isOccupied})">
                    ${seatId}
                </div>
            `;
        }
    }
    container.innerHTML = html;
}

// ===== 選擇/取消座位 =====
function toggleSeat(seatId, isOccupied) {
    if (isOccupied) {
        alert('此座位已被佔用');
        return;
    }

    const seatElement = document.querySelector(`[data-seat="${seatId}"]`);
    const isSelected = seatElement.classList.contains('selected');

    if (isSelected) {
        // 取消選擇
        seatElement.classList.remove('selected');
        selectedSeats = selectedSeats.filter(s => s !== seatId);
    } else {
        // 選擇座位（最多選擇 4 個）
        if (selectedSeats.length >= 4) {
            alert('最多只能選擇 4 個座位');
            return;
        }
        seatElement.classList.add('selected');
        selectedSeats.push(seatId);
    }

    // 更新座位數量顯示
    document.getElementById('seat-count').textContent = selectedSeats.length || 1;
}

// ===== 初始化乘客表單 =====
function initializePassengerForms() {
    const container = document.getElementById('passenger-forms');
    const count = selectedSeats.length;

    let html = '';
    for (let i = 0; i < count; i++) {
        html += `
            <div class="mb-3">
                <h6 class="fw-bold">乘客 ${i + 1} (座位 ${selectedSeats[i]})</h6>
                <div class="mb-2">
                    <label class="form-label">姓名 <span class="text-danger">*</span></label>
                    <input type="text" class="form-control" id="passenger-name-${i}"
                           placeholder="請輸入姓名" required>
                </div>
                <div class="mb-2">
                    <label class="form-label">電話 <span class="text-danger">*</span></label>
                    <input type="tel" class="form-control" id="passenger-phone-${i}"
                           placeholder="0912345678" pattern="[0-9]{10}" required>
                </div>
            </div>
            ${i < count - 1 ? '<hr>' : ''}
        `;
    }
    container.innerHTML = html;

    // 生成費用明細
    generatePriceBreakdown();
}

// ===== 生成費用明細 =====
function generatePriceBreakdown() {
    const ticketCount = selectedSeats.length;
    const baseFare = selectedCabinPrice * ticketCount;
    const airportTax = fees.airportTax * ticketCount;
    const fuelSurcharge = fees.fuelSurcharge * ticketCount;
    const serviceFee = fees.serviceFee * ticketCount;
    const total = baseFare + airportTax + fuelSurcharge + serviceFee;

    const html = `
        <div class="mb-2 d-flex justify-content-between">
            <span>機票費用 × ${ticketCount}</span>
            <span>NT$ ${baseFare.toLocaleString()}</span>
        </div>
        <div class="mb-2 d-flex justify-content-between">
            <span>機場稅</span>
            <span>NT$ ${airportTax.toLocaleString()}</span>
        </div>
        <div class="mb-2 d-flex justify-content-between">
            <span>燃油附加費</span>
            <span>NT$ ${fuelSurcharge.toLocaleString()}</span>
        </div>
        <div class="mb-2 d-flex justify-content-between">
            <span>服務費</span>
            <span>NT$ ${serviceFee.toLocaleString()}</span>
        </div>
        <hr>
        <div class="d-flex justify-content-between align-items-center">
            <h6 class="fw-bold mb-0">總計</h6>
            <h5 class="fw-bold text-primary mb-0">NT$ ${total.toLocaleString()}</h5>
        </div>
    `;

    // 更新兩個費用明細區域（步驟3和步驟4）
    const container3 = document.getElementById('price-breakdown');
    const container4 = document.getElementById('price-breakdown-payment');
    if (container3) container3.innerHTML = html;
    if (container4) container4.innerHTML = html;
}

// ===== 初始化付款表單（第4步）=====
function initializePaymentForm() {
    // 創建 3D 信用卡
    const cardContainer = document.getElementById('credit-card-container');
    cardContainer.innerHTML = `
        <div class="credit-card-3d" id="credit-card-3d">
            <div class="card-face card-front">
                <div class="card-chip"></div>
                <div class="card-logo">VISA</div>
                <div class="card-number" id="card-number-display">#### #### #### ####</div>
                <div class="card-info">
                    <div class="card-holder">
                        <div class="card-label">持卡人姓名</div>
                        <div class="card-value" id="card-holder-display">FULL NAME</div>
                    </div>
                    <div class="card-expiry">
                        <div class="card-label">有效期限</div>
                        <div class="card-value" id="card-expiry-display">MM/YY</div>
                    </div>
                </div>
            </div>
            <div class="card-face card-back">
                <div class="card-magnetic-strip"></div>
                <div class="card-cvv-section">
                    <div class="card-label">安全碼 (CVV)</div>
                    <div id="card-cvv-display">***</div>
                </div>
            </div>
        </div>
    `;

    // 綁定輸入事件
    setupCardInputHandlers();

    // 更新費用明細
    generatePriceBreakdown();
}

// ===== 設置信用卡輸入處理器 =====
function setupCardInputHandlers() {
    const card3D = document.getElementById('credit-card-3d');
    const cardNumberInput = document.getElementById('card-number');
    const cardHolderInput = document.getElementById('card-holder');
    const cardExpiryInput = document.getElementById('card-expiry');
    const cardCvvInput = document.getElementById('card-cvv');

    // 卡號輸入
    cardNumberInput.addEventListener('input', function(e) {
        let value = e.target.value.replace(/\s/g, '').replace(/\D/g, '');
        let formattedValue = value.match(/.{1,4}/g)?.join(' ') || value;
        e.target.value = formattedValue;

        // 更新卡片顯示
        const display = document.getElementById('card-number-display');
        if (display) {
            display.textContent = formattedValue || '#### #### #### ####';
        }
    });

    cardNumberInput.addEventListener('focus', () => {
        if (card3D) card3D.classList.remove('flipped');
    });

    // 持卡人姓名輸入
    cardHolderInput.addEventListener('input', function(e) {
        const value = e.target.value.toUpperCase();
        const display = document.getElementById('card-holder-display');
        if (display) {
            display.textContent = value || 'FULL NAME';
        }
    });

    cardHolderInput.addEventListener('focus', () => {
        if (card3D) card3D.classList.remove('flipped');
    });

    // 有效期限輸入
    cardExpiryInput.addEventListener('input', function(e) {
        let value = e.target.value.replace(/\D/g, '');
        if (value.length >= 2) {
            value = value.slice(0, 2) + '/' + value.slice(2, 4);
        }
        e.target.value = value;

        const display = document.getElementById('card-expiry-display');
        if (display) {
            display.textContent = value || 'MM/YY';
        }
    });

    cardExpiryInput.addEventListener('focus', () => {
        if (card3D) card3D.classList.remove('flipped');
    });

    // CVV 輸入（翻轉卡片）
    cardCvvInput.addEventListener('input', function(e) {
        let value = e.target.value.replace(/\D/g, '').slice(0, 3);
        e.target.value = value;

        const display = document.getElementById('card-cvv-display');
        if (display) {
            display.textContent = value || '***';
        }
    });

    cardCvvInput.addEventListener('focus', () => {
        if (card3D) card3D.classList.add('flipped');
    });

    cardCvvInput.addEventListener('blur', () => {
        if (card3D) card3D.classList.remove('flipped');
    });
}

// ===== 確認訂票 =====
async function confirmBooking() {
    // 驗證信用卡資訊
    const cardNumber = document.getElementById('card-number').value.trim();
    const cardHolder = document.getElementById('card-holder').value.trim();
    const cardExpiry = document.getElementById('card-expiry').value.trim();
    const cardCvv = document.getElementById('card-cvv').value.trim();

    if (!cardNumber || !cardHolder || !cardExpiry || !cardCvv) {
        alert('請填寫完整的信用卡資訊');
        return;
    }

    // 驗證卡號格式（16碼數字）
    const cardNumberDigits = cardNumber.replace(/\s/g, '');
    if (!/^\d{16}$/.test(cardNumberDigits)) {
        alert('卡號必須為16碼數字');
        return;
    }

    // 驗證有效期限格式（MM/YY）
    if (!/^\d{2}\/\d{2}$/.test(cardExpiry)) {
        alert('有效期限格式錯誤（例：12/25）');
        return;
    }

    // 驗證 CVV 格式（3碼數字）
    if (!/^\d{3}$/.test(cardCvv)) {
        alert('安全碼必須為3碼數字');
        return;
    }

    // 驗證乘客資訊
    const passengers = [];
    for (let i = 0; i < selectedSeats.length; i++) {
        const name = document.getElementById(`passenger-name-${i}`).value.trim();
        const phone = document.getElementById(`passenger-phone-${i}`).value.trim();

        if (!name || !phone) {
            alert(`請填寫完整的乘客 ${i + 1} 資訊`);
            return;
        }

        // 驗證電話格式
        const phoneRegex = /^[0-9]{10}$/;
        if (!phoneRegex.test(phone)) {
            alert(`乘客 ${i + 1} 的電話必須為10碼數字（例：0912345678）`);
            return;
        }

        passengers.push({ name, phone, seat: selectedSeats[i] });
    }

    // 計算總金額
    const ticketCount = selectedSeats.length;
    const baseFare = selectedCabinPrice * ticketCount;
    const totalAmount = baseFare + (fees.airportTax * ticketCount) +
                        (fees.fuelSurcharge * ticketCount) + (fees.serviceFee * ticketCount);

    // 準備訂票資料
    const bookingData = {
        Flight_Id: flightData.Flight_Id,  // 修正：使用 Flight_Id 而非 Id
        Cabin: selectedCabin,
        Price: totalAmount,
        Holder_Name: passengers[0].name,
        Holder_Mobile: passengers[0].phone,
        line_user_id: lineUserId
    };

    console.log('[DEBUG] 訂票資料:', bookingData);

    try {
        // 顯示處理中訊息
        if (confirm(`確認付款並訂購 ${flightData.No} 航班？\n總金額：NT$ ${totalAmount.toLocaleString()}\n\n信用卡：${cardNumber}\n持卡人：${cardHolder}`)) {
            const response = await fetch('/api/ticket/insert_liff', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(bookingData)
            });

            const result = await response.json();

            if (result.success) {
                alert('✅ 付款成功！訂票完成！');
                // 關閉 LIFF 視窗
                liff.closeWindow();
            } else {
                alert(`❌ 訂票失敗：${result.message || '未知錯誤'}`);
            }
        }
    } catch (error) {
        console.error('訂票失敗:', error);
        alert('❌ 訂票失敗，請稍後再試');
    }
}

// 頁面載入時初始化 LIFF
window.addEventListener('DOMContentLoaded', initializeLIFF);

