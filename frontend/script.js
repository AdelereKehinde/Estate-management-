// ================= CONFIG =================
const API_BASE = 'https://estate-management-3.onrender.com' || 'https: //localhost:8000';

// ================= UTILITIES =================
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function toast(msg, type = 'info') { // type: info | error | success
    const t = document.createElement('div');
    t.className = 'msg';
    t.style.borderColor = type === 'error' ? 'var(--red)' : type === 'success' ? 'var(--green)' : 'var(--stroke)';
    t.textContent = msg;
    $('#toast').appendChild(t);
    setTimeout(() => t.remove(), 3500);
}

function openModal(id) { $('#' + id).classList.add('open'); }

function closeModal(id) { $('#' + id).classList.remove('open'); }

function serializeForm(form) {
    const data = new FormData(form);
    const obj = {};
    for (const [k, v] of data.entries()) obj[k] = v;
    // cast numbers if numeric inputs
    $$('input[type="number"]', form).forEach(inp => { const k = inp.name; if (obj[k] !== undefined) obj[k] = Number(obj[k]); });
    return obj;
}

function setAuthUser(user) {
    if (user) { $('#userChip').textContent = `${user.full_name || 'User'} · ${user.role || ''}`; } else { $('#userChip').textContent = 'Guest'; }
}

function authHeader() {
    const token = localStorage.getItem('token');
    return token ? { 'Authorization': 'Bearer ' + token } : {};
}

async function apiFetch(path, options = {}) {
    const headers = Object.assign({ 'Content-Type': 'application/json' }, authHeader(), options.headers || {});
    const res = await fetch(API_BASE + path, Object.assign({}, options, { headers }));
    if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
    }
    const ct = res.headers.get('content-type') || '';
    return ct.includes('application/json') ? res.json() : res.text();
}

// ================ ROUTING (simple SPA) ================
const routes = ['dashboard', 'estates', 'properties', 'units', 'tenants', 'leases', 'billing', 'maintenance', 'auth'];

function show(route) {
    routes.forEach(r => {
        const v = $('#view-' + r);
        if (v) v.style.display = r === route ? '' : 'none';
    });
    $$('#nav button').forEach(b => b.classList.toggle('active', b.dataset.route === route));
    localStorage.setItem('route', route);
    if (route !== 'auth') { loadAllFor(route); }
}

// ================ LOADERS / DASHBOARD ================
async function loadDashboard() {
    try {
        const [units, tenants, invoices] = await Promise.all([
            apiFetch('/units'), apiFetch('/tenants'), apiFetch('/invoices?status='),
        ]);
        const occupied = units.filter(u => u.occupied).length;
        const occupancy = units.length ? Math.round((occupied / units.length) * 100) : 0;
        $('#kpi-occupancy').textContent = occupancy + '%';
        $('#kpi-tenants').textContent = tenants.length;
        const pending = invoices.filter(i => i.status === 'pending').length;
        $('#kpi-pending').textContent = pending;
        const paidTotal = invoices.filter(i => i.status === 'paid').reduce((s, i) => s + (i.amount || 0), 0);
        $('#kpi-revenue').textContent = paidTotal.toLocaleString();
        drawRevenueChart(invoices.filter(i => i.status === 'paid'));
        renderRecentInvoices(invoices.slice(-8).reverse());
    } catch (e) { toast(e.message, 'error'); }
}

function drawRevenueChart(paid) {
    const canvas = $('#chartRevenue');
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    // group by month
    const byMonth = {};
    for (const inv of paid) {
        const d = new Date(inv.due_date);
        const k = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
        byMonth[k] = (byMonth[k] || 0) + inv.amount;
    }
    const labels = Object.keys(byMonth).sort();
    const values = labels.map(k => byMonth[k]);
    // axes
    const w = canvas.width = canvas.clientWidth;
    const h = canvas.height = 160;
    const pad = 30;
    const max = Math.max(...values, 100);
    ctx.strokeStyle = '#223';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad, h - pad);
    ctx.lineTo(w - pad, h - pad);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(pad, h - pad);
    ctx.lineTo(pad, pad / 2);
    ctx.stroke();
    // line
    ctx.beginPath();
    values.forEach((v, i) => {
        const x = pad + (i * (w - 2 * pad)) / Math.max(values.length - 1, 1);
        const y = h - pad - (v / max) * (h - 2 * pad);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = '#6ee7b7';
    ctx.lineWidth = 2;
    ctx.stroke();
    // gradient fill
    const g = ctx.createLinearGradient(0, pad, 0, h - pad);
    g.addColorStop(0, 'rgba(16,185,129,.35)');
    g.addColorStop(1, 'rgba(16,185,129,0)');
    ctx.fillStyle = g;
    ctx.lineTo(w - pad, h - pad);
    ctx.lineTo(pad, h - pad);
    ctx.closePath();
    ctx.fill();
    // labels
    ctx.fillStyle = '#9fb8ff';
    ctx.font = '10px sans-serif';
    labels.forEach((lab, i) => {
        const x = pad + (i * (w - 2 * pad)) / Math.max(values.length - 1, 1);
        ctx.fillText(lab, x - 14, h - 10);
    });
}

function renderRecentInvoices(list) {
    const tbody = $('#recentInvoices');
    tbody.innerHTML = '';
    list.forEach(i => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${i.ref||'-'}</td><td>${i.lease_id}</td><td>${i.due_date}</td><td>${i.amount.toLocaleString()}</td><td>${i.status}</td>
        <td><button class="btn-secondary" onclick="prefillPayment(${i.id}, ${i.amount})">Pay</button></td>`;
        tbody.appendChild(tr);
    })
}

// ================ ENTITY LOADERS ================
async function loadEstates() {
    try {
        const data = await apiFetch('/estates');
        const tbody = $('#tbl-estates');
        tbody.innerHTML = '';
        data.forEach(e => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${e.id}</td><td>${e.name}</td><td>${e.location}</td>`;
            tbody.appendChild(tr);
        });
    } catch (e) { toast(e.message, 'error'); }
}

async function loadProperties() {
    try {
        const data = await apiFetch('/properties');
        const tbody = $('#tbl-properties');
        tbody.innerHTML = '';
        data.forEach(p => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${p.id}</td><td>${p.code}</td><td>${p.address}</td><td>${p.estate_id}</td>`;
            tbody.appendChild(tr);
        });
    } catch (e) { toast(e.message, 'error'); }
}

async function loadUnits() {
    try {
        const data = await apiFetch('/units');
        const tbody = $('#tbl-units');
        tbody.innerHTML = '';
        data.forEach(u => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${u.id}</td><td>${u.property_id}</td><td>${u.label}</td><td>${u.bedrooms}</td><td>${u.occupied? 'Yes':'No'}</td>`;
            tbody.appendChild(tr);
        });
    } catch (e) { toast(e.message, 'error'); }
}

async function loadTenants() {
    try {
        const data = await apiFetch('/tenants');
        const tbody = $('#tbl-tenants');
        tbody.innerHTML = '';
        data.forEach(t => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${t.id}</td><td>${t.full_name}</td><td>${t.email}</td><td>${t.phone||''}</td>`;
            tbody.appendChild(tr);
        });
    } catch (e) { toast(e.message, 'error'); }
}

async function loadLeases() {
    try {
        const data = await apiFetch('/leases'); // not implemented list endpoint in API; fallback to invoices join based views
    } catch { /* ignore */ }
    try {
        const invoices = await apiFetch('/invoices');
        const byLease = {};
        invoices.forEach(i => {
            if (!byLease[i.lease_id]) byLease[i.lease_id] = [];
            byLease[i.lease_id].push(i);
        });
        const tbody = $('#tbl-leases');
        tbody.innerHTML = '';
        Object.keys(byLease).forEach(id => {
            const arr = byLease[id];
            const inv = arr[0];
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${id}</td><td>${inv ? inv.lease_id : '-'}</td><td>-</td><td>${inv ? inv.due_date : '-'}</td><td>-</td><td>${inv ? inv.amount.toLocaleString() : '-'}</td><td>-</td><td>-</td>
          <td><button class="btn" onclick="openModal('createInvoiceModal'); $('#modal-form-invoice-gen [name=\'lease_id\']').value=${id};">Generate</button></td>`;
            tbody.appendChild(tr);
        });
    } catch (e) { toast(e.message, 'error'); }
}

async function loadInvoices() {
    try {
        const status = $('#filter-invoice-status').value;
        const path = status ? `/invoices?status=${encodeURIComponent(status)}` : '/invoices';
        const data = await apiFetch(path);
        const tbody = $('#tbl-invoices');
        tbody.innerHTML = '';
        data.forEach(i => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${i.id}</td><td>${i.lease_id}</td><td>${i.due_date}</td><td>${i.amount.toLocaleString()}</td><td>${i.status}</td><td>${i.ref||''}</td>`;
            tbody.appendChild(tr);
        });
    } catch (e) { toast(e.message, 'error'); }
}

async function loadTickets() {
    try { const data = await apiFetch('/maintenance/tickets'); /* list not in API; we will show only created ones via cache */ } catch { /* ignore */ }
}

async function loadAllFor(route) {
    if (!localStorage.getItem('token')) { show('auth'); return; }
    setAuthUser(JSON.parse(localStorage.getItem('user') || '{}'));
    switch (route) {
        case 'dashboard':
            await loadDashboard();
            break;
        case 'estates':
            await loadEstates();
            break;
        case 'properties':
            await loadProperties();
            break;
        case 'units':
            await loadUnits();
            break;
        case 'tenants':
            await loadTenants();
            break;
        case 'leases':
            await loadLeases();
            break;
        case 'billing':
            await loadInvoices();
            break;
        case 'maintenance':
            await loadTickets();
            break;
    }
}

// ================ FORMS HANDLERS ================
$('#form-estate').addEventListener('submit', async(e) => {
    e.preventDefault();
    try {
        const body = serializeForm(e.target);
        await apiFetch('/estates', { method: 'POST', body: JSON.stringify(body) });
        toast('Estate created', 'success');
        loadEstates();
        show('estates');
    } catch (err) { toast(err.message, 'error'); }
});

$('#form-property').addEventListener('submit', async(e) => {
    e.preventDefault();
    try {
        const body = serializeForm(e.target);
        await apiFetch('/properties', { method: 'POST', body: JSON.stringify(body) });
        toast('Property created', 'success');
        loadProperties();
    } catch (err) { toast(err.message, 'error'); }
});

$('#form-unit').addEventListener('submit', async(e) => {
    e.preventDefault();
    try {
        const body = serializeForm(e.target);
        await apiFetch('/units', { method: 'POST', body: JSON.stringify(body) });
        toast('Unit created', 'success');
        loadUnits();
    } catch (err) { toast(err.message, 'error'); }
});

$('#form-tenant').addEventListener('submit', async(e) => {
    e.preventDefault();
    try {
        const body = serializeForm(e.target);
        await apiFetch('/tenants', { method: 'POST', body: JSON.stringify(body) });
        toast('Tenant created', 'success');
        loadTenants();
    } catch (err) { toast(err.message, 'error'); }
});

$('#modal-form-tenant').addEventListener('submit', async(e) => {
    e.preventDefault();
    try {
        const body = serializeForm(e.target);
        await apiFetch('/tenants', { method: 'POST', body: JSON.stringify(body) });
        toast('Tenant created', 'success');
        closeModal('createTenantModal');
        loadTenants();
    } catch (err) { toast(err.message, 'error'); }
});

$('#form-lease').addEventListener('submit', async(e) => {
    e.preventDefault();
    try {
        const body = serializeForm(e.target);
        await apiFetch('/leases', { method: 'POST', body: JSON.stringify(body) });
        toast('Lease created', 'success');
        loadLeases();
    } catch (err) { toast(err.message, 'error'); }
});

$('#modal-form-lease').addEventListener('submit', async(e) => {
    e.preventDefault();
    try {
        const body = serializeForm(e.target);
        await apiFetch('/leases', { method: 'POST', body: JSON.stringify(body) });
        toast('Lease created', 'success');
        closeModal('createLeaseModal');
        loadLeases();
    } catch (err) { toast(err.message, 'error'); }
});

$('#modal-form-invoice-gen').addEventListener('submit', async(e) => {
    e.preventDefault();
    try {
        const body = serializeForm(e.target);
        await apiFetch(`/leases/${body.lease_id}/generate-invoices`, { method: 'POST' });
        toast('Invoices generated', 'success');
        closeModal('createInvoiceModal');
        loadInvoices();
    } catch (err) { toast(err.message, 'error'); }
});

$('#form-payment').addEventListener('submit', async(e) => {
    e.preventDefault();
    try {
        const body = serializeForm(e.target);
        await apiFetch('/payments', { method: 'POST', body: JSON.stringify(body) });
        toast('Payment recorded', 'success');
        loadInvoices();
    } catch (err) { toast(err.message, 'error'); }
});

$('#form-ticket').addEventListener('submit', async(e) => {
    e.preventDefault();
    try {
        const body = serializeForm(e.target);
        await apiFetch('/maintenance/tickets', { method: 'POST', body: JSON.stringify(body) });
        toast('Ticket created', 'success');
        loadTickets();
    } catch (err) { toast(err.message, 'error'); }
});

$('#modal-form-ticket').addEventListener('submit', async(e) => {
    e.preventDefault();
    try {
        const body = serializeForm(e.target);
        await apiFetch('/maintenance/tickets', { method: 'POST', body: JSON.stringify(body) });
        toast('Ticket created', 'success');
        closeModal('ticketModal');
        loadTickets();
    } catch (err) { toast(err.message, 'error'); }
});

function prefillPayment(invoiceId, amount) {
    const form = $('#form-payment');
    form.invoice_id.value = invoiceId;
    form.amount.value = amount;
    show('billing');
}

// ================ AUTH ================
$('#form-register').addEventListener('submit', async(e) => {
    e.preventDefault();
    try {
        const body = serializeForm(e.target);
        body.role = 'admin';
        const res = await apiFetch('/auth/register', { method: 'POST', body: JSON.stringify(body) });
        localStorage.setItem('token', res.access_token);
        localStorage.setItem('user', JSON.stringify({ full_name: body.full_name, role: 'admin' }));
        toast('Admin registered & logged in', 'success');
        setAuthUser(JSON.parse(localStorage.getItem('user')));
        show('dashboard');
    } catch (err) { toast(err.message, 'error'); }
});

$('#form-login').addEventListener('submit', async(e) => {
    e.preventDefault();
    try {
        const body = serializeForm(e.target);
        const res = await apiFetch('/auth/login', { method: 'POST', body: JSON.stringify(body) });
        localStorage.setItem('token', res.access_token);
        // We don't have a /me endpoint; store the email as display
        localStorage.setItem('user', JSON.stringify({ full_name: body.email.split('@')[0], role: 'admin' }));
        toast('Logged in', 'success');
        setAuthUser(JSON.parse(localStorage.getItem('user')));
        show('dashboard');
    } catch (err) { toast(err.message, 'error'); }
});

$('#logoutBtn').addEventListener('click', () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    toast('Logged out', 'success');
    show('auth');
    setAuthUser(null);
});

// ================ NAV / TABS ================
$$('#nav button').forEach(btn => btn.addEventListener('click', () => show(btn.dataset.route)));

function initTabs() {
    $$('.tabs').forEach(tabs => {
        const tabBtns = $$('.tab', tabs);
        tabBtns.forEach(b => b.addEventListener('click', () => {
            tabBtns.forEach(x => x.classList.toggle('active', x === b));
            const section = tabs.parentElement; // section/view
            $$('#' + section.id + ' > [id^=tab-]').forEach(panel => panel.style.display = 'none');
            $('#' + 'tab-' + b.dataset.tab).style.display = '';
        }))
    })
}

// ================ SEARCH (client side demo) ================
$('#globalSearch').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') toast('Global search is a UI demo. Use module lists/filters to find records.');
});

// ================ STARTUP ================
(function() {
    initTabs();
    const route = localStorage.getItem('route') || 'dashboard';
    if (!localStorage.getItem('token')) { show('auth'); } else { show(route); }
})();