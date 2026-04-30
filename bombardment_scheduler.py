"""
Fix My Name Online — Bombardment Scheduler
Manages the daily/weekly content generation and publishing queue.
Copyright (c) 2026 MadisonJade Pty Ltd. All Rights Reserved.
"""

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import threading
import time


# =============================================================================
# QUEUE ITEM DATA STRUCTURE
# =============================================================================

@dataclass
class QueueItem:
    """A single item in the content queue."""
    id: str
    customer_id: str
    keyword: str
    content_type: str  # 'article', 'social', 'all'
    platforms: List[str]
    status: str = "queued"  # queued, published, failed, paused
    priority: int = 5  # 1-10, higher = more urgent
    scheduled_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    published_at: Optional[datetime] = None
    result_url: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    metadata: Dict = field(default_factory=dict)


@dataclass
class ScheduleConfig:
    """Configuration for a customer's bombardment schedule."""
    customer_id: str
    mode: str = "manual"  # manual, daily, weekly, bulk
    enabled: bool = False
    articles_per_day: int = 5
    social_per_day: int = 5
    stagger_hours: int = 2  # Min hours between posts to same platform
    peak_hours: List[int] = field(default_factory=lambda: [9, 10, 11, 14, 15, 16])  # Posting hours
    weekends: bool = True
    platforms: List[str] = field(default_factory=lambda: ["linkedin", "twitter", "medium"])
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None


# =============================================================================
# QUEUE STORAGE
# =============================================================================

def get_queue_dir() -> str:
    """Get the queue storage directory."""
    queue_dir = os.path.join(os.path.dirname(__file__), "data", "queue")
    os.makedirs(queue_dir, exist_ok=True)
    return queue_dir


def load_queue(customer_id: str) -> List[QueueItem]:
    """Load queue for a customer."""
    queue_file = os.path.join(get_queue_dir(), f"{customer_id}.json")
    if os.path.exists(queue_file):
        with open(queue_file) as f:
            data = json.load(f)
            return [QueueItem(**item) for item in data]
    return []


def save_queue(customer_id: str, queue: List[QueueItem]):
    """Save queue for a customer."""
    queue_file = os.path.join(get_queue_dir(), f"{customer_id}.json")
    with open(queue_file, "w") as f:
        json.dump([vars(item) for item in queue], f, indent=2, default=str)


def load_schedule(customer_id: str) -> ScheduleConfig:
    """Load schedule config for a customer."""
    schedule_file = os.path.join(get_queue_dir(), f"{customer_id}_schedule.json")
    if os.path.exists(schedule_file):
        with open(schedule_file) as f:
            data = json.load(f)
            return ScheduleConfig(**data)
    return ScheduleConfig(customer_id=customer_id)


def save_schedule(schedule: ScheduleConfig):
    """Save schedule config."""
    schedule_file = os.path.join(get_queue_dir(), f"{schedule.customer_id}_schedule.json")
    with open(schedule_file, "w") as f:
        json.dump(vars(schedule), f, indent=2, default=str)


# =============================================================================
# QUEUE MANAGER
# =============================================================================

class BombardmentQueue:
    """
    Manages the content generation and publishing queue for FMNOL.
    
    Key features:
    - Queue items for scheduled publishing
    - Stagger posts to avoid platform bans
    - Priority queue for urgent content
    - Retry logic for failed items
    - Peak hour scheduling
    """
    
    def __init__(self, customer_id: str):
        self.customer_id = customer_id
        self.queue = load_queue(customer_id)
        self.schedule = load_schedule(customer_id)
    
    def add_item(
        self,
        keyword: str,
        platforms: List[str],
        content_type: str = "all",
        priority: int = 5,
        scheduled_time: Optional[datetime] = None
    ) -> QueueItem:
        """Add an item to the queue."""
        
        item = QueueItem(
            id=str(uuid.uuid4()),
            customer_id=self.customer_id,
            keyword=keyword,
            content_type=content_type,
            platforms=platforms,
            status="queued",
            priority=priority,
            scheduled_time=scheduled_time or self._get_next_slot(platforms)
        )
        
        self.queue.append(item)
        self.queue.sort(key=lambda x: (x.priority, x.scheduled_time or datetime.max), reverse=True)
        save_queue(self.customer_id, self.queue)
        
        return item
    
    def bulk_add(
        self,
        keyword: str,
        platforms: List[str],
        count: int = 5,
        content_type: str = "all"
    ) -> List[QueueItem]:
        """Add multiple items to the queue (bulk mode)."""
        
        items = []
        for i in range(count):
            item = self.add_item(
                keyword=keyword,
                platforms=platforms,
                content_type=content_type,
                priority=5,
                scheduled_time=None  # Auto-scheduled with stagger
            )
            items.append(item)
        
        return items
    
    def get_next(self) -> Optional[QueueItem]:
        """Get the next item ready for publishing."""
        now = datetime.now()
        
        for item in self.queue:
            if item.status == "queued":
                if item.scheduled_time and item.scheduled_time > now:
                    continue
                return item
        
        return None
    
    def mark_published(self, item_id: str, result_url: str = None):
        """Mark an item as published."""
        for item in self.queue:
            if item.id == item_id:
                item.status = "published"
                item.published_at = datetime.now()
                item.result_url = result_url
                break
        
        save_queue(self.customer_id, self.queue)
    
    def mark_failed(self, item_id: str, error: str):
        """Mark an item as failed with retry logic."""
        for item in self.queue:
            if item.id == item_id:
                item.retry_count += 1
                if item.retry_count >= 3:
                    item.status = "failed"
                    item.error = error
                else:
                    # Reschedule with backoff
                    item.scheduled_time = datetime.now() + timedelta(hours=item.retry_count * 2)
                break
        
        save_queue(self.customer_id, self.queue)
    
    def pause(self, item_id: str):
        """Pause an item."""
        for item in self.queue:
            if item.id == item_id:
                item.status = "paused"
                break
        save_queue(self.customer_id, self.queue)
    
    def resume(self, item_id: str):
        """Resume a paused item."""
        for item in self.queue:
            if item.id == item_id:
                item.status = "queued"
                item.scheduled_time = self._get_next_slot(item.platforms)
                break
        save_queue(self.customer_id, self.queue)
    
    def clear_completed(self):
        """Remove completed items from queue."""
        self.queue = [item for item in self.queue if item.status != "published"]
        save_queue(self.customer_id, self.queue)
    
    def get_stats(self) -> Dict:
        """Get queue statistics."""
        stats = {
            "total": len(self.queue),
            "queued": len([i for i in self.queue if i.status == "queued"]),
            "published": len([i for i in self.queue if i.status == "published"]),
            "failed": len([i for i in self.queue if i.status == "failed"]),
            "paused": len([i for i in self.queue if i.status == "paused"]),
        }
        return stats
    
    def _get_next_slot(self, platforms: List[str]) -> datetime:
        """Calculate next available publishing slot."""
        
        now = datetime.now()
        stagger = timedelta(hours=self.schedule.stagger_hours)
        
        # Find last published time for these platforms
        last_times = {}
        for item in self.queue:
            if item.status == "published":
                for p in item.platforms:
                    if p in platforms:
                        last_times[p] = item.published_at
        
        # Get the latest last published time
        latest = now
        for p in platforms:
            if p in last_times:
                slot = last_times[p] + stagger
                if slot > latest:
                    latest = slot
        
        # Check if within peak hours
        if not self._is_peak_hour(latest):
            # Find next peak hour
            latest = self._next_peak_hour(latest)
        
        return latest
    
    def _is_peak_hour(self, dt: datetime) -> bool:
        """Check if datetime is within peak posting hours."""
        if not self.schedule.weekends and dt.weekday() >= 5:
            return False
        return dt.hour in self.schedule.peak_hours
    
    def _next_peak_hour(self, dt: datetime) -> datetime:
        """Find the next available peak hour slot."""
        candidate = dt
        
        for _ in range(48):  # Max 48 hours lookahead
            if self._is_peak_hour(candidate):
                return candidate
            candidate += timedelta(hours=1)
        
        return candidate


# =============================================================================
# SCHEDULER (for cron-style operation)
# =============================================================================

class BombardmentScheduler:
    """
    Background scheduler for automated bombardment mode.
    
    In production, this would run as a background process
    or be triggered by cron jobs.
    """
    
    def __init__(self, customer_id: str):
        self.customer_id = customer_id
        self.queue = BombardmentQueue(customer_id)
        self.running = False
        self._thread = None
    
    def start(self):
        """Start the scheduler in background thread."""
        if self.running:
            return
        
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def _run(self):
        """Main scheduler loop."""
        while self.running:
            try:
                # Check if schedule is enabled
                if not self.queue.schedule.enabled:
                    time.sleep(60)
                    continue
                
                # Get next item
                item = self.queue.get_next()
                
                if item:
                    # Process the item
                    self._process_item(item)
                else:
                    # No items ready, check if we need to generate more
                    self._check_and_generate()
                
                # Sleep before next check
                time.sleep(30)
                
            except Exception as e:
                print(f"Scheduler error: {e}")
                time.sleep(60)
    
    def _process_item(self, item: QueueItem):
        """Process a queue item (generate + publish)."""
        
        try:
            # Generate content
            from content_generator import generate_content
            
            content = generate_content(item.keyword)
            
            if "error" in content and "fallback" not in content:
                raise Exception(f"Content generation failed: {content['error']}")
            
            if "fallback" in content:
                content = content["fallback"]
            
            # Publish to platforms
            from fps_publisher import quick_publish_to_fps
            
            result = quick_publish_to_fps(
                keyword=item.keyword,
                content=content,
                customer_id=item.customer_id,
                site="firstpagestrategy",
                status="publish"
            )
            
            if result.success:
                self.queue.mark_published(item.id, result.post_url)
            else:
                self.queue.mark_failed(item.id, result.error)
                
        except Exception as e:
            self.queue.mark_failed(item.id, str(e))
    
    def _check_and_generate(self):
        """Check if we need to generate more content."""
        
        stats = self.queue.get_stats()
        
        # If queue is running low, generate more
        if stats["queued"] < self.queue.schedule.articles_per_day:
            for _ in range(self.queue.schedule.articles_per_day - stats["queued"]):
                self.queue.bulk_add(
                    keyword=self.queue.schedule.get("default_keyword", ""),
                    platforms=self.queue.schedule.platforms,
                    count=1,
                    content_type="all"
                )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_daily_schedule(customer_id: str, keyword: str, platforms: List[str]) -> ScheduleConfig:
    """Create a daily bombardment schedule."""
    
    schedule = ScheduleConfig(
        customer_id=customer_id,
        mode="daily",
        enabled=True,
        articles_per_day=5,
        social_per_day=5,
        stagger_hours=2,
        peak_hours=[9, 10, 11, 14, 15, 16],
        weekends=True,
        platforms=platforms
    )
    
    schedule.next_run = datetime.now()
    save_schedule(schedule)
    
    # Seed the queue
    queue = BombardmentQueue(customer_id)
    for _ in range(schedule.articles_per_day):
        queue.bulk_add(
            keyword=keyword,
            platforms=platforms,
            count=1,
            content_type="all"
        )
    
    return schedule


def create_weekly_schedule(customer_id: str, keyword: str, platforms: List[str]) -> ScheduleConfig:
    """Create a weekly bombardment schedule."""
    
    schedule = ScheduleConfig(
        customer_id=customer_id,
        mode="weekly",
        enabled=True,
        articles_per_day=50,  # Bulk generate for week
        social_per_day=50,
        stagger_hours=4,
        peak_hours=[9, 10, 11, 14, 15, 16],
        weekends=True,
        platforms=platforms
    )
    
    schedule.next_run = datetime.now()
    save_schedule(schedule)
    
    # Seed the queue
    queue = BombardmentQueue(customer_id)
    queue.bulk_add(
        keyword=keyword,
        platforms=platforms,
        count=schedule.articles_per_day,
        content_type="all"
    )
    
    return schedule


def pause_all(customer_id: str):
    """Pause all scheduled publishing."""
    queue = BombardmentQueue(customer_id)
    for item in queue.queue:
        if item.status == "queued":
            queue.pause(item.id)
    
    schedule = load_schedule(customer_id)
    schedule.enabled = False
    save_schedule(schedule)


def resume_all(customer_id: str):
    """Resume all scheduled publishing."""
    queue = BombardmentQueue(customer_id)
    for item in queue.queue:
        if item.status == "paused":
            queue.resume(item.id)
    
    schedule = load_schedule(customer_id)
    schedule.enabled = True
    save_schedule(schedule)


# =============================================================================
# DAILY REPORT
# =============================================================================

def generate_daily_report(customer_id: str) -> str:
    """Generate a daily bombardment report for Sarah to send."""
    
    queue = BombardmentQueue(customer_id)
    schedule = load_schedule(customer_id)
    stats = queue.get_stats()
    
    report = f"""
╔══════════════════════════════════════════════════════════════════╗
║     FIX MY NAME ONLINE — DAILY BOMBARDMENT REPORT              ║
╚══════════════════════════════════════════════════════════════════╝

Date: {datetime.now().strftime('%d %B %Y')}
Customer ID: {customer_id}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUEUE STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total Items: {stats['total']}
Queued: {stats['queued']}
Published Today: {stats['published']}
Failed: {stats['failed']}
Paused: {stats['paused']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCHEDULE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Mode: {schedule.mode.upper()}
Status: {'ACTIVE' if schedule.enabled else 'PAUSED'}
Articles/Day: {schedule.articles_per_day}
Social/Day: {schedule.social_per_day}
Peak Hours: {', '.join(str(h) + ':00' for h in schedule.peak_hours)}
Weekends: {'Yes' if schedule.weekends else 'No'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TODAY'S TOP PLATFORMS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
    
    # Count by platform
    platform_counts = {}
    for item in queue.queue:
        for p in item.platforms:
            platform_counts[p] = platform_counts.get(p, 0) + 1
    
    for p, count in sorted(platform_counts.items(), key=lambda x: -x[1])[:5]:
        report += f"• {p}: {count} items\n"
    
    report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RECOMMENDATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
    
    if stats['queued'] < 10:
        report += "⚠️ Queue running low. Consider bulk-generating more content.\n"
    
    if stats['failed'] > stats['published'] * 0.2:
        report += "⚠️ High failure rate. Check platform credentials.\n"
    
    if not schedule.enabled:
        report += "📝 Schedule is paused. Resume to continue bombardment.\n"
    
    if stats['published'] > 0:
        report += f"✅ Great progress! {stats['published']} pieces published today.\n"
    
    report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Next scheduled run: {schedule.next_run.strftime('%d %B %Y %H:%M') if schedule.next_run else 'N/A'}

This report was generated by Hermes Agent for FixMyNameOnline.
© 2026 MadisonJade Pty Ltd. All Rights Reserved.
"""
    
    return report
