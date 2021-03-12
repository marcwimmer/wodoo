<?php

/**
 * Sample plugin to try out some hooks.
 * This performs an automatic login if accessed from localhost
 *
 * @license GNU GPLv3+
 * @author Thomas Bruederli
 */
class autologon extends rcube_plugin
{
    public $task = 'login';

    /**
     * Plugin initialization
     */
    public function init()
    {
        $this->add_hook('startup', [$this, 'startup']);
        $this->add_hook('authenticate', [$this, 'authenticate']);
    }

    /**
     * 'startup' hook handler
     *
     * @param array $args Hook arguments
     *
     * @return array Hook arguments
     */
    function startup($args)
    {
        // change action to login
        if (empty($_SESSION['user_id'])) {
            $args['action'] = 'login';
        }

        return $args;
    }

    /**
     * 'authenticate' hook handler
     *
     * @param array $args Hook arguments
     *
     * @return array Hook arguments
     */
    function authenticate($args)
    {
        $args['user']        = 'postmaster';
        $args['pass']        = 'postmaster';
        $args['host']        = 'mail';
        $args['cookiecheck'] = false;
        $args['valid']       = true;

        return $args;
    }
}
