<?php
/**
 * Created by JetBrains PhpStorm.
 * User: milan
 * Date: 7/12/13
 * Time: 8:57 AM
 * To change this template use File | Settings | File Templates.
 */

require_once('inc/vCalendar.php');

// compatibility with phpunit 6
if (!class_exists('\PHPUnit_Framework_TestCase') &&
    class_exists('\PHPUnit\Framework\TestCase')) {
    class_alias('\PHPUnit\Framework\TestCase', '\PHPUnit_Framework_TestCase');
}

class myCalendarTest extends PHPUnit_Framework_TestCase {

    function getData($filename){
        $file = fopen($filename, 'r');
        $data = fread($file, filesize($filename));
        fclose($file);
        return $data;
    }

    function test1(){


        $mycalendar = new vCalendar($this->getData('tests/data/0000-Setup-PUT-collection.test'));
        $test = $mycalendar->Render();

        $timezones = $mycalendar->GetComponents('VTIMEZONE',true);
        $components = $mycalendar->GetComponents('VTIMEZONE',false);


        $resources = array();
        foreach($components as $comp){

            $uid = $comp->GetPValue('UID');
            $resources[$uid][] = $comp;


        }

        foreach($resources as $key => $res){
            $testcal = new vCalendar();
            $testcal->SetComponents($res);
            $t = $testcal->Render();
            $t = $testcal->Render();
        }

        $mycalendar->Render();
    }


    function test2(){

        $data = explode("\n",$this->getData('tests/data/0244-MOZ-POST-FB.test'));

        $data = implode($data, "\r\n");

        $mycalendar = new vCalendar($data);
//        foreach($mycalendar->GetComponents() as $comp){
//            $next = $comp->GetComponents();
//            if(isset($next)){
//                foreach($next as $comp2){
//                    $comp2->GetComponents();
//                    $comp2->GetProperties();
//                }
//            }
//
//            $comp->GetProperties();
//        }
        //$test = $mycalendar->Render();
        $property = $mycalendar->GetProperties()[0];
        $value = $property->Value();
        $name = $property->Name();


        $this->assertStringEndsNotWith("\r", $value);
    }

}
