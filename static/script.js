const minPriceSlider = document.getElementById("min-price");
const maxPriceSlider = document.getElementById("max-price");
const priceRangeText = document.getElementById("price-range");
const resultBody = document.getElementById("result-body");

// 模擬航班資料（假資料）
const flights = [
    { from: "台北松山機場", to: "日本羽田機場", airline: "華航", date: "2025-03-15", price: 8000 },
    { from: "台北松山機場", to: "日本羽田機場", airline: "長榮", date: "2025-03-18", price: 10000 },
    { from: "桃園國際機場", to: "日本成田機場", airline: "星宇", date: "2025-03-20", price: 12000 },
    { from: "高雄小港機場", to: "韓國仁川機場", airline: "華航", date: "2025-03-25", price: 7500 }
];

// 更新價格範圍
function updatePriceRange() {
    let minValue = parseInt(minPriceSlider.value);
    let maxValue = parseInt(maxPriceSlider.value);

    if (minValue > maxValue - 1000) {
        minPriceSlider.value = maxValue - 1000;
        minValue = maxValue - 1000;
    }
    if (maxValue < minValue + 1000) {
        maxPriceSlider.value = minValue + 1000;
        maxValue = minValue + 1000;
    }

    priceRangeText.textContent = `NT$ ${minValue} - NT$ ${maxValue}`;
}

// 監聽滑動條變化
minPriceSlider.addEventListener("input", updatePriceRange);
maxPriceSlider.addEventListener("input", updatePriceRange);

// 查詢航班
function submitForm() {
    const departureDate = document.getElementById("departure-date").value;
    const departureCity = document.getElementById("departure-city").value;
    const destinationCity = document.getElementById("destination-city").value;

    const selectedAirlines = [];
    if (document.getElementById("china-airlines").checked) selectedAirlines.push("華航");
    if (document.getElementById("star-airlines").checked) selectedAirlines.push("星宇");
    if (document.getElementById("eva-airlines").checked) selectedAirlines.push("長榮");

    const minPrice = parseInt(minPriceSlider.value);
    const maxPrice = parseInt(maxPriceSlider.value);

    const filteredFlights = flights.filter(flight => 
        flight.from === departureCity &&
        flight.to === destinationCity &&
        selectedAirlines.includes(flight.airline) &&
        flight.price >= minPrice &&
        flight.price <= maxPrice
    );

    resultBody.innerHTML = "";

    if (filteredFlights.length === 0) {
        resultBody.innerHTML = `<tr><td colspan="5">無符合條件的航班</td></tr>`;
    } else {
        filteredFlights.forEach(flight => {
            resultBody.innerHTML += `
                <tr>
                    <td>${flight.from}</td>
                    <td>${flight.to}</td>
                    <td>${flight.airline}</td>
                    <td>${flight.date}</td>
                    <td>NT$ ${flight.price}</td>
                </tr>
            `;
        });
    }
}
