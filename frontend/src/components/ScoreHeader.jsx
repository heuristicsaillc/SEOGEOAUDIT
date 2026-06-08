// Big score + grade header shown at the top of a report.
import React from "react"; // React core

// Map a letter grade to a colour class for the badge
function gradeClass(grade) {
  if (grade === "A" || grade === "B") return "grade good"; // Green-ish
  if (grade === "C" || grade === "D") return "grade warn"; // Amber
  return "grade bad"; // Red for F
}

export default function ScoreHeader({ report }) {
  return (
    <div className="score-header">
      {/* Circular score + grade badge */}
      <div className={gradeClass(report.grade)}>
        <div className="grade-letter">{report.grade}</div>
        <div className="grade-score">{report.score}/100</div>
      </div>

      {/* Title + excluded-parameter note */}
      <div className="score-meta">
        <h2>{report.kind.toUpperCase()} Report</h2>
        <p>
          {report.manual_count} parameter(s) excluded from the score
          (Manual / Not Measured).
        </p>
      </div>
    </div>
  );
}
