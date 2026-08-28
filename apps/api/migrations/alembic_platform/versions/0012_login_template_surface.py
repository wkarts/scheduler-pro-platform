"""Allow LOGIN as a first-class template surface."""
from alembic import op
revision="platform_0012_login_surface"
down_revision="platform_0011_global_templates"
branch_labels=None
depends_on=None
def upgrade():
 op.execute("alter table global_content_templates drop constraint if exists ck_global_content_template_surface")
 op.execute("alter table global_content_templates add constraint ck_global_content_template_surface check(surface in ('LANDING','BOOKING','LOGIN'))")
 op.execute("update platform_permissions set description='Criar, versionar e publicar modelos globais de Landing Page, Página de Agendamento e Login' where key='templates.manage'")
def downgrade():
 op.execute("delete from global_content_template_versions where template_id in (select id from global_content_templates where surface='LOGIN')")
 op.execute("delete from global_content_templates where surface='LOGIN'")
 op.execute("alter table global_content_templates drop constraint if exists ck_global_content_template_surface")
 op.execute("alter table global_content_templates add constraint ck_global_content_template_surface check(surface in ('LANDING','BOOKING'))")
