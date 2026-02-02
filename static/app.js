let commodityGroups = [];
let currentRequestId = null;
let orderLineCount = 0;
let suggestTimeout = null;

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    await loadCommodityGroups();
    addOrderLine();
    loadRequests();
});

// Debounced auto-suggest for commodity group
function debouncedSuggest() {
    clearTimeout(suggestTimeout);
    suggestTimeout = setTimeout(autoSuggestCommodityGroup, 800);
}

async function autoSuggestCommodityGroup() {
    const title = document.getElementById('title').value;
    const orderLines = [];
    document.querySelectorAll('#order-lines-container .order-line').forEach(line => {
        const desc = line.querySelector('.ol-desc').value;
        if (desc) orderLines.push({ description: desc });
    });

    if (!title && orderLines.length === 0) return;

    const suggestionDiv = document.getElementById('commodity-suggestion');
    suggestionDiv.classList.remove('hidden');
    suggestionDiv.innerHTML = '<em>AI is suggesting commodity group...</em>';

    try {
        const res = await fetch('/api/suggest-commodity-group', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title,
                vendor_name: document.getElementById('vendor_name').value,
                order_lines: orderLines
            })
        });
        const result = await res.json();

        const group = commodityGroups.find(g => g.id === result.commodity_group_id);
        document.getElementById('commodity_group').value = result.commodity_group_id;
        suggestionDiv.innerHTML = `<strong>Auto-selected:</strong> ${group ? group.category + ' > ' + group.name : result.commodity_group_id}<br><em>${result.reason}</em>`;
    } catch (err) {
        suggestionDiv.innerHTML = '<em style="color: #6b7280;">Could not auto-suggest</em>';
    }
}

async function loadCommodityGroups() {
    const res = await fetch('/api/commodity-groups');
    commodityGroups = await res.json();
    const select = document.getElementById('commodity_group');
    commodityGroups.forEach(g => {
        const opt = document.createElement('option');
        opt.value = g.id;
        opt.textContent = `${g.category} > ${g.name}`;
        select.appendChild(opt);
    });
}

function showTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.tab[onclick="showTab('${tab}')"]`).classList.add('active');
    document.getElementById('tab-new').classList.toggle('hidden', tab !== 'new');
    document.getElementById('tab-list').classList.toggle('hidden', tab !== 'list');
    if (tab === 'list') loadRequests();
}

function addOrderLine(data = {}) {
    orderLineCount++;
    const container = document.getElementById('order-lines-container');
    const line = document.createElement('div');
    line.className = 'order-line';
    line.id = `order-line-${orderLineCount}`;
    line.innerHTML = `
        <input type="text" placeholder="Description" class="ol-desc" value="${data.description || ''}" oninput="debouncedSuggest()" required>
        <input type="number" placeholder="0.00" class="ol-price" step="0.01" value="${data.unit_price || ''}" oninput="updateTotals()" required>
        <input type="number" placeholder="1" class="ol-amount" value="${data.amount || ''}" oninput="updateTotals()" required>
        <input type="text" placeholder="pcs" class="ol-unit" value="${data.unit || 'pcs'}">
        <input type="number" placeholder="0.00" class="ol-total" value="${data.total_price || ''}" readonly>
        <button type="button" class="btn btn-danger" onclick="removeOrderLine(${orderLineCount})">X</button>
    `;
    container.appendChild(line);
}

function removeOrderLine(id) {
    const line = document.getElementById(`order-line-${id}`);
    if (line && document.querySelectorAll('.order-line:not(.order-line-header)').length > 1) {
        line.remove();
        updateTotals();
    }
}

function updateTotals() {
    let total = 0;
    document.querySelectorAll('#order-lines-container .order-line').forEach(line => {
        const price = parseFloat(line.querySelector('.ol-price').value) || 0;
        const amount = parseInt(line.querySelector('.ol-amount').value) || 0;
        const lineTotal = price * amount;
        line.querySelector('.ol-total').value = lineTotal.toFixed(2);
        total += lineTotal;
    });
    document.getElementById('total-cost').textContent = total.toFixed(2);
}

async function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const status = document.getElementById('upload-status');
    const uploadArea = document.querySelector('.upload-area');

    // Show loading spinner
    status.className = 'upload-status extracting';
    status.innerHTML = '<span class="spinner"></span>Extracting data from PDF...';
    uploadArea.classList.add('loading');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/api/extract-document', { method: 'POST', body: formData });
        if (!res.ok) throw new Error('Extraction failed');
        const data = await res.json();

        if (data.vendor_name) document.getElementById('vendor_name').value = data.vendor_name;
        if (data.vat_id) document.getElementById('vat_id').value = data.vat_id;
        if (data.department) document.getElementById('department').value = data.department;
        if (data.title) document.getElementById('title').value = data.title;
        if (data.suggested_commodity_group_id) {
            document.getElementById('commodity_group').value = data.suggested_commodity_group_id;
        }

        if (data.order_lines && data.order_lines.length > 0) {
            document.getElementById('order-lines-container').innerHTML = '';
            orderLineCount = 0;
            data.order_lines.forEach(ol => addOrderLine(ol));
            // Don't call updateTotals() here - use the extracted total_price from Gesamt column directly
        }

        // Use extracted total_cost if available (includes VAT, shipping, etc.)
        if (data.total_cost) {
            document.getElementById('total-cost').textContent = data.total_cost.toFixed(2);
        }

        if (data.suggested_commodity_group_id) {
            const group = commodityGroups.find(g => g.id === data.suggested_commodity_group_id);
            const suggestionDiv = document.getElementById('commodity-suggestion');
            suggestionDiv.classList.remove('hidden');
            suggestionDiv.innerHTML = `<strong>Auto-selected:</strong> ${group ? group.category + ' > ' + group.name : data.suggested_commodity_group_id}`;
        }

        status.className = 'upload-status success';
        status.innerHTML = 'Data extracted successfully!';
    } catch (err) {
        status.className = 'upload-status error';
        status.innerHTML = `Error: ${err.message}`;
    } finally {
        uploadArea.classList.remove('loading');
    }
}

async function submitRequest(event) {
    event.preventDefault();

    const orderLines = [];
    document.querySelectorAll('#order-lines-container .order-line').forEach(line => {
        orderLines.push({
            description: line.querySelector('.ol-desc').value,
            unit_price: parseFloat(line.querySelector('.ol-price').value) || 0,
            amount: parseInt(line.querySelector('.ol-amount').value) || 0,
            unit: line.querySelector('.ol-unit').value || 'pcs',
            total_price: parseFloat(line.querySelector('.ol-total').value) || 0
        });
    });

    const request = {
        requestor_name: document.getElementById('requestor_name').value,
        title: document.getElementById('title').value,
        vendor_name: document.getElementById('vendor_name').value,
        vat_id: document.getElementById('vat_id').value,
        commodity_group_id: document.getElementById('commodity_group').value,
        order_lines: orderLines,
        total_cost: parseFloat(document.getElementById('total-cost').textContent) || 0,
        department: document.getElementById('department').value
    };

    try {
        const res = await fetch('/api/requests', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request)
        });

        if (res.ok) {
            alert('Request submitted successfully!');
            document.getElementById('request-form').reset();
            document.getElementById('order-lines-container').innerHTML = '';
            orderLineCount = 0;
            addOrderLine();
            document.getElementById('total-cost').textContent = '0.00';
            document.getElementById('commodity-suggestion').classList.add('hidden');
            showTab('list');
        } else {
            throw new Error('Submission failed');
        }
    } catch (err) {
        alert('Error submitting request: ' + err.message);
    }
}

async function loadRequests() {
    const res = await fetch('/api/requests');
    const requests = await res.json();

    const tbody = document.getElementById('requests-table');
    tbody.innerHTML = requests.length === 0
        ? '<tr><td colspan="10" style="text-align: center; color: #6b7280;">No requests yet</td></tr>'
        : requests.map(r => {
            const orderLines = r.data.order_lines || [];
            const escapeHtml = (str) => String(str).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            const ordersHtml = orderLines.length > 0
                ? orderLines.map((ol, i) =>
                    `<div style="${i < orderLines.length - 1 ? 'margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid #e5e7eb;' : ''}">
                        ${escapeHtml(ol.description)}<br>
                        <span style="color: #6b7280; font-size: 12px;">
                            ${ol.unit_price.toFixed(2)} x ${ol.amount} ${ol.unit} = ${ol.total_price.toFixed(2)}
                        </span>
                    </div>`
                ).join('')
                : '-';
            const vatId = r.data.vat_id && r.data.vat_id.trim() ? r.data.vat_id : '-';

            return `
            <tr style="vertical-align: top;">
                <td>${r.id}</td>
                <td>${r.data.title}</td>
                <td>${r.data.vendor_name}</td>
                <td>${vatId}</td>
                <td>${r.data.requestor_name}</td>
                <td>${r.data.department || '-'}</td>
                <td>${ordersHtml}</td>
                <td>${r.data.total_cost.toFixed(2)}</td>
                <td><span class="status ${getStatusClass(r.status)}">${r.status}</span></td>
                <td><button class="btn btn-secondary" onclick="openStatusModal('${r.id}')">Update</button></td>
            </tr>
        `;
        }).join('');
}

function getStatusClass(status) {
    if (status === 'Open') return 'status-open';
    if (status === 'In Progress') return 'status-progress';
    return 'status-closed';
}

async function openStatusModal(requestId) {
    currentRequestId = requestId;
    const res = await fetch(`/api/requests/${requestId}`);
    const req = await res.json();

    document.getElementById('new-status').value = req.status;
    document.getElementById('status-history-display').innerHTML = '<strong>Status History:</strong><br>' +
        req.status_history.map(h => `${h.status} - ${new Date(h.timestamp).toLocaleString()}`).join('<br>');
    document.getElementById('status-modal').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('status-modal').classList.add('hidden');
    currentRequestId = null;
}

async function confirmStatusUpdate() {
    const newStatus = document.getElementById('new-status').value;
    await fetch(`/api/requests/${currentRequestId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
    });
    closeModal();
    loadRequests();
}
