
frappe.ui.form.on('Indicator', {
    validate(frm) {
        if (frm.doc.target && frm.doc.actual) {
            let progress = (frm.doc.actual / frm.doc.target) * 100;
            frm.set_value('progress_percent', Number.isFinite(progress) ? progress.toFixed(2) : 0);
            let status = 'Red';
            if (progress >= 90) status = 'Green';
            else if (progress >= 70) status = 'Yellow';
            frm.set_value('status', status);
        } else {
            frm.set_value('progress_percent', 0);
            frm.set_value('status', 'Red');
        }
    }
});
