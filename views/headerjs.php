<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
   "http://www.w3.org/TR/html4/loose.dtd">

<html lang="fr">
<head>
	<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
	<link rel="stylesheet" type="text/css" href="/style.css">
	<title><?=$title?></title>
	
    <script src="/prototype.js" language="JavaScript" ></script>
	<script src="/reflection.js" type="text/javascript" ></script>
    
	<script src="/updateimages.js" type="text/javascript" ></script>
  	<script type="text/javascript" charset="utf-8">

	/*
	 * Chargement de la page
	 */
	(function() {
      Event.observe(document, 'dom:loaded', function() {
	  load($('idpiece').getAttribute('value'));
      new PeriodicalExecuter(getRemoteContent, <?=$this->config->item('LIGHT_REFRESH')?>);
	  })
    })()
  </script>
</head>
<body>
    <div id="conteneur">
    	<input type="hidden" id="idpiece" value="<?=$piece?>"/>

      <div id="header">
        Mon Header
      </div>
      <div id="haut">
       </div>
      <div id="gauche">
         <ul id="menuhaut">
         <?
            foreach($menu as $id=>$nom)
            {
                echo "<li><a href=\"http://localhost/index.php/piece/lookup/".$id."\">".$nom."</a></li>";
            }
        ?>
        </ul>
      
      </div>
      <div id="droite">
        <ul id="menudroit">
        <? 
        $cap = $this->config->item('CAPACITIES');
        foreach($capacites as $c)
        {
            echo "<li><a href=\"http://localhost/index.php/piece/".$cap[$c]."/".$piece."\">".$c."</a></li>";
        }
        ?>
        </ul>
      </div>
      <div id="centre">
      	<div id="titre">
      		<h2>
      			<center>
      			<?=$name_piece?>	
				</center>
      		</h2>
			
      	</div>
		<center>
		
