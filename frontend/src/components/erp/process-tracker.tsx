import { cn } from '@/lib/utils';
import { Check } from 'lucide-react';

export interface ProcessStep {
  key: string;
  label: string;
}

interface ProcessTrackerProps {
  steps: ProcessStep[];
  currentStep: string;
  className?: string;
}

export function ProcessTracker({ steps, currentStep, className }: ProcessTrackerProps) {
  const currentIndex = steps.findIndex((s) => s.key === currentStep);

  return (
    <div className={cn('flex items-center', className)}>
      {steps.map((step, index) => {
        const isDone = index < currentIndex;
        const isCurrent = index === currentIndex;

        return (
          <div key={step.key} className="flex items-center flex-1 last:flex-none">
            {/* Step dot */}
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  'flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold border-2 transition-colors',
                  isDone
                    ? 'bg-green-600 border-green-600 text-white'
                    : isCurrent
                      ? 'bg-blue-600 border-blue-600 text-white'
                      : 'bg-white border-slate-300 text-slate-400',
                )}
              >
                {isDone ? <Check className="h-3.5 w-3.5" /> : <span>{index + 1}</span>}
              </div>
              <span
                className={cn(
                  'mt-1.5 text-xs font-medium whitespace-nowrap',
                  isDone
                    ? 'text-green-600'
                    : isCurrent
                      ? 'text-blue-600'
                      : 'text-slate-400',
                )}
              >
                {step.label}
              </span>
            </div>

            {/* Connector line */}
            {index < steps.length - 1 && (
              <div
                className={cn(
                  'flex-1 h-0.5 mx-2 mb-5',
                  isDone ? 'bg-green-400' : 'bg-slate-200',
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// Predefined steps for common object types
export const ITEM_STEPS: ProcessStep[] = [
  { key: 'Entwurf', label: 'Entwurf' },
  { key: 'Freigegeben', label: 'Freigegeben' },
  { key: 'Ersetzt', label: 'Ersetzt' },
];

