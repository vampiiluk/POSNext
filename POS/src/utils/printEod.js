import { silentPrintDoc } from "./printInvoice";
import { getSavedPrinterName } from "./qzTray";

const EOD_PRINT_FORMAT = "POS Next EOD Report";

export async function printEODReport(closingShiftName) {
	if (getSavedPrinterName()) {
		await silentPrintDoc("POS Closing Shift", closingShiftName, EOD_PRINT_FORMAT);
	} else {
		const params = new URLSearchParams({
			doctype: "POS Closing Shift",
			name: closingShiftName,
			format: EOD_PRINT_FORMAT,
			no_letterhead: 1,
			_lang: "en",
			trigger_print: 1,
			_t: Date.now(),
		});
		
		const printWindow = window.open(`/printview?${params}`, "_blank", "width=800,height=600");
		if (!printWindow) {
			throw new Error("Popup blocked — check your browser settings.");
		}
	}
}
