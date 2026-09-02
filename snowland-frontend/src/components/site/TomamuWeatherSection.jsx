import React from 'react';

const weatherItems = [
  { label: "天氣", icon: "❆", value: "降雪", type: "icon" },
  { label: "氣溫", value: "-10", unit: "°C", type: "metric" },
  { label: "積雪量", value: "146", unit: "cm", type: "metric" },
  { label: "24小時降雪", value: "13", unit: "cm", type: "metric" },
  { label: "雪質", value: "粉雪", type: "text" },
  { label: "纜車運行狀態", value: "開放", type: "text" },
];

function TomamuWeatherSection() {
  return (
    <section className="bg-[#e9eef3] text-[#1f3b6d]">
      <div className="max-w-6xl mx-auto px-6 py-12">
        <div className="space-y-10">
          <div className="grid gap-10 lg:grid-cols-[auto,1fr] items-center">
            <div className="text-xl md:text-2xl font-semibold text-[#1f3b6d]">2026.01.21</div>
            <div className="grid gap-6 lg:grid-cols-6">
              {weatherItems.map((item) => (
                <div key={item.label} className="flex flex-col h-full">
                  <div className="flex items-center justify-between text-sm font-semibold text-[#1f3b6d]">
                    <span>{item.label}</span>
                    <span className="ml-4 h-px flex-1 bg-[#1f3b6d]" />
                  </div>
                  {item.type === "icon" && (
                    <div className="mt-auto pt-4 flex items-center justify-start gap-3 text-[#1f3b6d]">
                      <span className="text-5xl leading-none" aria-hidden="true">
                        {item.icon}
                      </span>
                      <div className="text-lg font-semibold">{item.value}</div>
                    </div>
                  )}
                  {item.type === "metric" && (
                    <div className="mt-auto pt-6 text-4xl font-semibold text-[#1f3b6d]">
                      {item.value}
                      <span className="text-xl ml-1">{item.unit}</span>
                    </div>
                  )}
                  {item.type === "text" && (
                    <div className="mt-auto pt-6 text-lg font-semibold text-[#1f3b6d]">
                      {item.value}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default TomamuWeatherSection;
