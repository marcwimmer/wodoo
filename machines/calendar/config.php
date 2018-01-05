<?php
  $c->default_locale = "de_DE";
  $c->pg_connect[] = 'host=calendar_db user=davical password=davical dbname=davical';
  $c->dbg = array( 'statistics' => 1, 'request' => 1, 'response' => 1 );
?>
