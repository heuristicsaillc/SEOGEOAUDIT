// Renders one category as a table: Parameter | What to check | Rating | Recommendation.
import React from "react"; // React core

// Map a rating string to a CSS class for the coloured pill
function ratingClass(rating) {
  switch (rating) {
    case "Meeting":
      return "pill meeting"; // Green
    case "Partial":
      return "pill partial"; // Amber
    case "Not Meeting":
      return "pill not-meeting"; // Red
    case "Manual":
      return "pill manual"; // Grey
    default:
      return "pill not-measured"; // Grey (Not Measured)
  }
}

export default function CategoryTable({ category }) {
  return (
    <section className="category">
      {/* Category header with its sub-score */}
      <div className="category-head">
        <h3>{category.title}</h3>
        <span className="category-score">{category.score}/100</span>
      </div>

      <table className="param-table">
        <thead>
          <tr>
            <th>Parameter</th>
            <th>What to check</th>
            <th>Rating</th>
            <th>Recommendation</th>
          </tr>
        </thead>
        <tbody>
          {category.parameters.map((p, idx) => (
            // Manual/Not Measured rows are visually de-emphasised (excluded from score)
            <tr
              key={idx}
              className={p.rating === "Manual" || p.rating === "Not Measured" ? "excluded" : ""}
            >
              <td>
                <div className="param-name">{p.name}</div>
                {/* Detection method + confidence as a small caption */}
                <div className="param-method">
                  {p.method}
                  {p.confidence ? ` · ${p.confidence}` : ""}
                </div>
              </td>
              <td>{p.what_to_check}</td>
              <td>
                <span className={ratingClass(p.rating)}>{p.rating}</span>
                {/* Show the priority next to actionable ratings */}
                {p.priority && <span className="priority">{p.priority}</span>}
              </td>
              <td>
                {p.fix_where || p.recommendation ? (
                  <>
                    {p.fix_where && (
                      <div className="param-fix-where">
                        <strong>Where:</strong> {p.fix_where}
                      </div>
                    )}
                    {p.recommendation && (
                      <div className="param-fix-change">
                        {p.fix_where ? <strong>Change: </strong> : null}
                        {p.recommendation}
                      </div>
                    )}
                    {p.detail && p.detail !== p.recommendation && (
                      <div className="muted param-detail">
                        <strong>Evidence:</strong> {p.detail}
                      </div>
                    )}
                  </>
                ) : (
                  <span className="muted">{p.detail}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
