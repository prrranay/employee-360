import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Modal } from '../common/Modal';
import { attendanceApi } from '../../api/client';

interface CorrectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultDate?: string;
}

export const CorrectionModal: React.FC<CorrectionModalProps> = ({
  isOpen,
  onClose,
  defaultDate = ''
}) => {
  const queryClient = useQueryClient();
  const [date, setDate] = useState(defaultDate);
  const [exceptionType, setExceptionType] = useState('Missed Check-out');
  const [status, setStatus] = useState('Present');
  const [inTime, setInTime] = useState('09:00');
  const [outTime, setOutTime] = useState('18:00');
  const [reason, setReason] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  React.useEffect(() => {
    if (defaultDate) {
      setDate(defaultDate);
    }
  }, [defaultDate]);

  const mutation = useMutation({
    mutationFn: () =>
      attendanceApi.requestCorrection({
        activity_date: date,
        exception_type: exceptionType,
        requested_status: status,
        requested_in_time: inTime || undefined,
        requested_out_time: outTime || undefined,
        reason: reason.trim()
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teamExceptions'] });
      queryClient.invalidateQueries({ queryKey: ['exceptionsPage'] });
      queryClient.invalidateQueries({ queryKey: ['employeeActivity'] });
      queryClient.invalidateQueries({ queryKey: ['todayAttendance'] });
      onClose();
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.message || err?.message || 'Failed to submit regularization request.';
      setErrorMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!date || !reason.trim()) {
      setErrorMsg('Date and Reason are mandatory.');
      return;
    }
    mutation.mutate();
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Attendance Regularization Request">
      <form onSubmit={handleSubmit} className="space-y-4">
        {errorMsg && (
          <div className="rounded-lg bg-rose-50 p-3 text-xs font-medium text-rose-700">
            {errorMsg}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-slate-700">Activity Date</label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-300 p-2.5 text-xs text-slate-800 focus:border-indigo-500 focus:outline-none"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Correction Category</label>
            <select
              value={exceptionType}
              onChange={(e) => setExceptionType(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-300 p-2.5 text-xs text-slate-800 focus:border-indigo-500 focus:outline-none"
            >
              <option value="Missed Check-out">Missed Check-out</option>
              <option value="Missed Check-in">Missed Check-in</option>
              <option value="Late Arrival">Late Arrival Dispute</option>
              <option value="Unexcused Absence">Unexcused Absence Regularization</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-xs font-semibold text-slate-700">Requested Status</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-300 p-2.5 text-xs text-slate-800 focus:border-indigo-500 focus:outline-none"
            >
              <option value="Present">Present (Full Day)</option>
              <option value="Half Day">Half Day</option>
              <option value="On Leave">On Leave</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Actual IN Time</label>
            <input
              type="time"
              value={inTime}
              onChange={(e) => setInTime(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-300 p-2.5 text-xs text-slate-800 focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700">Actual OUT Time</label>
            <input
              type="time"
              value={outTime}
              onChange={(e) => setOutTime(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-300 p-2.5 text-xs text-slate-800 focus:border-indigo-500 focus:outline-none"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700">Reason / Explanation</label>
          <textarea
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Please detail why the punch was missed or disputed (e.g. Onsite client visit without mobile network, biometric reader offline, emergency checkout)..."
            className="mt-1 w-full rounded-xl border border-slate-300 p-2.5 text-xs text-slate-800 focus:border-indigo-500 focus:outline-none"
            required
          />
        </div>

        <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 text-[11px] text-slate-500">
          <p className="font-semibold text-slate-700">Audit & Regularization Policy:</p>
          <p className="mt-0.5">
            Requests are automatically routed to your reporting manager. Upon manager approval, correction punches with an audit tag are preserved and work duration is recalculated. Historical records are never silently erased.
          </p>
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={mutation.isPending}
            className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
          >
            {mutation.isPending ? 'Submitting Request...' : 'Submit Regularization'}
          </button>
        </div>
      </form>
    </Modal>
  );
};
