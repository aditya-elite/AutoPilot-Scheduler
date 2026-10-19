export function downloadCsvFromBackend() {
  // The backend streams the CSV directly (see /analytics/export/schedule.csv);
  // this just triggers the browser download using the authenticated client.
  const token = localStorage.getItem('autopilot_token')
  const url = `/api/analytics/export/schedule.csv`
  fetch(url, { headers: { Authorization: `Bearer ${token}` } })
    .then((res) => res.blob())
    .then((blob) => {
      const link = document.createElement('a')
      link.href = window.URL.createObjectURL(blob)
      link.download = 'autopilot_schedule.csv'
      link.click()
    })
}

export async function exportGanttToPdf(assignments) {
  // jsPDF + autotable are only needed for this one action, and they're
  // heavy (~200kB) — load them on demand instead of bundling them into
  // every page load.
  const [{ default: jsPDF }, { default: autoTable }] = await Promise.all([
    import('jspdf'),
    import('jspdf-autotable'),
  ])

  const doc = new jsPDF({ orientation: 'landscape' })
  doc.setFontSize(16)
  doc.text('AutoPilot Scheduler — Master Schedule', 14, 16)
  doc.setFontSize(10)
  doc.text(`Generated ${new Date().toLocaleString()}`, 14, 22)

  const rows = assignments.map((a) => [
    a.job_code,
    a.task_name,
    a.machine_code,
    new Date(a.scheduled_start).toLocaleString(),
    new Date(a.scheduled_end).toLocaleString(),
    a.status,
    a.violates_constraint ? 'Yes' : 'No',
  ])

  autoTable(doc, {
    startY: 28,
    head: [['Job', 'Task', 'Machine', 'Start', 'End', 'Status', 'Violation']],
    body: rows,
    styles: { fontSize: 8 },
    headStyles: { fillColor: [79, 209, 197] },
  })

  doc.save('autopilot_schedule.pdf')
}
