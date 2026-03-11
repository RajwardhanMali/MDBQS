import React from 'react'

interface RelationshipBadgeProps {
  label?: string
  type?: 'positive' | 'negative' | 'neutral'
}

const RelationshipBadge: React.FC<RelationshipBadgeProps> = ({ label = 'Relationship', type = 'neutral' }) => {
  return (
    <span className={`relationship-badge badge-${type}`}>
      {label}
    </span>
  )
}

export default RelationshipBadge
