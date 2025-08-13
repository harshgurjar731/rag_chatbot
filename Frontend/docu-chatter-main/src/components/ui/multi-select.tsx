// components/ui/multi-select.tsx

import React from "react";

interface MultiSelectProps {
  options: { label: string; value: string | number }[];
  selected: { label: string; value: string | number }[];
  onChange: (selected: { label: string; value: string | number }[]) => void;
  placeholder?: string;
}

export const MultiSelect: React.FC<MultiSelectProps> = ({
  options,
  selected,
  onChange,
  placeholder,
}) => {
  const toggleOption = (option: { label: string; value: string | number }) => {
    const isSelected = selected.some((s) => s.value === option.value);
    if (isSelected) {
      onChange(selected.filter((s) => s.value !== option.value));
    } else {
      onChange([...selected, option]);
    }
  };

  return (
    <div className="border rounded p-2 min-h-[40px]">
      <div className="mb-2 text-sm text-gray-500">{placeholder}</div>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          const isSelected = selected.some((s) => s.value === opt.value);
          return (
            <button
              key={opt.value}
              onClick={() => toggleOption(opt)}
              className={`px-2 py-1 rounded text-sm border ${
                isSelected
                  ? "bg-blue-100 border-blue-500 text-blue-700"
                  : "bg-white border-gray-300 text-gray-600"
              }`}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
};
