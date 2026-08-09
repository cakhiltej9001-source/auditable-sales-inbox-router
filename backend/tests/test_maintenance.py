from sqlmodel import Session, SQLModel, create_engine, select

from app.models import IngestRun, ProcessedEmail, ProcessingStatus, SkippedEmail, TaskRecord
from app.services.maintenance import purge_candidate_data


def test_purge_candidate_data_is_scoped_to_one_canonical_identity(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'maintenance.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for candidate, suffix in [
            ("cakhiltej9001@gmail.com", "target"),
            ("other@example.com", "other"),
        ]:
            task = TaskRecord(
                external_task_id=f"tsk-{suffix}",
                candidate_id=candidate,
                thread_id=f"thread-{suffix}",
                source_email_id=f"mail-{suffix}",
                assignee_id="u_rohit",
                category="smb_enquiry",
                priority="low",
                title="Demo",
            )
            session.add(task)
            session.flush()
            session.add(ProcessedEmail(
                candidate_id=candidate,
                run_id=f"run-{suffix}",
                source_email_id=f"mail-{suffix}",
                thread_id=f"thread-{suffix}",
                status=ProcessingStatus.created,
                category="smb_enquiry",
                task_record_id=task.id,
                reason="Created",
                raw_email_json="{}",
            ))
            session.add(SkippedEmail(
                candidate_id=candidate,
                run_id=f"run-{suffix}",
                source_email_id=f"skip-{suffix}",
                thread_id=f"skip-thread-{suffix}",
                skip_type="newsletter",
                reason="Skipped",
                subject="Digest",
                from_email="news@example.com",
            ))
            session.add(IngestRun(
                run_id=f"run-{suffix}",
                candidate_id=candidate,
                processed=2,
                tasks_created=1,
                tasks_updated=0,
                skipped=1,
                duplicate_count=0,
                error_count=0,
            ))
        session.commit()

        counts = purge_candidate_data(session, "cakhiltej9001+demo@gmail.com")
        assert counts == {
            "processed_emails": 1,
            "skipped_emails": 1,
            "ingest_runs": 1,
            "tasks": 1,
        }
        assert len(session.exec(select(TaskRecord)).all()) == 1
        assert session.exec(select(TaskRecord)).one().candidate_id == "other@example.com"
