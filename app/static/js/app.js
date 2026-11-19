// Campus Resource Optimization System - Client Interactions

function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.add('active');
    }
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.remove('active');
    }
}

// Close modals when clicking outside content
window.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('active');
    }
});

// Dynamic Table Filter
function filterTable(inputId, tableId) {
    const input = document.getElementById(inputId);
    const filter = input.value.toLowerCase();
    const table = document.getElementById(tableId);
    const tr = table.getElementsByTagName('tr');

    for (let i = 1; i < tr.length; i++) {
        let tdList = tr[i].getElementsByTagName('td');
        let matched = false;
        for (let j = 0; j < tdList.length; j++) {
            if (tdList[j]) {
                const text = tdList[j].textContent || tdList[j].innerText;
                if (text.toLowerCase().indexOf(filter) > -1) {
                    matched = true;
                    break;
                }
            }
        }
        tr[i].style.display = matched ? "" : "none";
    }
}

// ============================================================================
// LIVE UPDATES: poll /api/live so status changes made by the booking scheduler
// (slot ended -> resource AVAILABLE) appear without reloading the page.
// ============================================================================
const LIVE_POLL_MS = 5000;
let serverClockOffsetMs = 0;  // server time minus browser time

function parseDbTime(s) {
    return s ? new Date(s.replace(' ', 'T')) : null;
}

function formatDuration(ms) {
    const totalMin = Math.max(0, Math.ceil(ms / 60000));
    const d = Math.floor(totalMin / 1440), h = Math.floor((totalMin % 1440) / 60), m = totalMin % 60;
    if (d) return `${d}d ${h}h`;
    if (h) return `${h}h ${m}m`;
    return `${m}m`;
}

function renderAvailabilityCell(cell) {
    const now = new Date(Date.now() + serverClockOffsetMs);
    const status = cell.dataset.status;
    const freeAt = parseDbTime(cell.dataset.freeAt);
    const nextAt = parseDbTime(cell.dataset.nextAt);
    let html = '';
    if (status === 'BOOKED' && freeAt) {
        html = `<span class="avail-busy">Free at ${cell.dataset.freeAt.slice(0, 16)}</span><br><small>in ${formatDuration(freeAt - now)}</small>`;
    } else if (status === 'AVAILABLE') {
        html = '<span class="avail-free">Free now</span>';
        if (nextAt) html += `<br><small>Next booking ${cell.dataset.nextAt.slice(0, 16)}</small>`;
    } else if (status === 'MAINTENANCE') {
        html = '<small>Under maintenance</small>';
    } else if (status === 'INACTIVE') {
        html = '<small>Not bookable</small>';
    }
    cell.innerHTML = html;
}

function setBadge(badge, status) {
    if (!badge || badge.textContent.trim() === status) return false;
    badge.className = `badge badge-${status.toLowerCase()} js-status`;
    badge.textContent = status;
    const row = badge.closest('tr');
    if (row) {
        row.classList.remove('row-flash');
        void row.offsetWidth;  // restart the animation
        row.classList.add('row-flash');
    }
    return true;
}

async function pollLive() {
    try {
        const res = await fetch('/api/live', { cache: 'no-store' });
        if (res.status === 401) { location.href = '/login'; return; }
        if (!res.ok) throw new Error(res.statusText);
        const data = await res.json();
        serverClockOffsetMs = parseDbTime(data.server_time) - Date.now();

        data.resources.forEach(r => {
            const row = document.querySelector(`tr[data-resource-id="${r.resource_id}"]`);
            if (!row) return;
            setBadge(row.querySelector('.js-status'), r.status);
            const select = row.querySelector('select[name="status"]');
            if (select && document.activeElement !== select) select.value = r.status;
            const cell = row.querySelector('.js-availability');
            cell.dataset.status = r.status;
            cell.dataset.freeAt = r.free_at || '';
            cell.dataset.nextAt = r.next_booking_at || '';
            renderAvailabilityCell(cell);
        });

        data.bookings.forEach(b => {
            const row = document.querySelector(`tr[data-booking-id="${b.booking_id}"]`);
            if (row && setBadge(row.querySelector('.js-status'), b.status) && !['CONFIRMED', 'PENDING'].includes(b.status)) {
                const cancelForm = row.querySelector('form[action^="/bookings/cancel"]');
                if (cancelForm) cancelForm.outerHTML = '<span style="color: var(--text-muted); font-size: 0.8rem;">None</span>';
            }
        });

        Object.entries(data.kpis).forEach(([key, value]) => {
            document.querySelectorAll(`[data-kpi="${key}"]`).forEach(el => { el.textContent = value; });
        });

        document.getElementById('liveIndicator')?.classList.remove('offline');
    } catch (e) {
        document.getElementById('liveIndicator')?.classList.add('offline');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const cells = () => document.querySelectorAll('.js-availability');
    cells().forEach(renderAvailabilityCell);
    if (document.querySelector('[data-resource-id], [data-booking-id], [data-kpi]')) {
        pollLive();
        setInterval(pollLive, LIVE_POLL_MS);
        setInterval(() => cells().forEach(renderAvailabilityCell), 1000);  // tick the countdowns
    }
});
